"""Mutationsprüfung: jede Änderung an einer Rechenstelle muss mindestens einen Test fehlschlagen lassen.

Aufruf (aus dem Repo-Ordner, mit dem Test-venv): python tools/mutation_check.py [--jobs 4] [--only Teil]
Jeder Mutant läuft in einer Kopie des Repos (Temp-Ordner), die Tests des Kerns (ohne App-Tests) laufen mit -x. Ergebnis: pro Mutant
„gefunden“ (ein Test scheitert) oder „ÜBERLEBT“; Rückgabewert 1, wenn ein Mutant überlebt."""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS = ["tests/test_rng.py", "tests/test_sim.py", "tests/test_oracle_bunching.py", "tests/test_evaluation.py"]

# (Datei, alter Text, neuer Text, Beschreibung[, n-te Stelle]); jeder alte Text kommt in der Datei genau einmal vor, sonst mit Stellenangabe.
# Bewusst NICHT in der Liste (gleichwertige Änderungen, im README begründet):
#  - `g = ta - ld` durch `g = t - ld`: unterscheidet sich nur, wenn der Bus am Steg warten muss (selten, nur ohne Regelung).
#  - Newton-Schritt der Wachstumsrate halbieren: das Verfahren konvergiert mit 200 Schritten zur selben Wurzel.
#  - Schranke `share > 0.5` im Median der Zeit bis zum Pulk und andere Anzeigeschwellen ohne Rechenwirkung.
MUTANTS = [
    ("bun_sim.py", "D = d0 + s * k1\n", "D = d0 + s * k1 * 2.0\n", "Zustiegszeit verdoppeln"),
    ("bun_sim.py", "ready = ta + D\n", "ready = ta + D + 0.1\n", "Haltezeit verlängern"),
    ("bun_sim.py", "ta = t if t >= ld + delta else ld + delta", "ta = t", "Einzelsteg entfernen"),
    ("bun_sim.py", "else poisson(rd, lam * g)\n", "else poisson(rd, lam * g * 1.1)\n", "Fahrgastrate vor dem Halt erhöhen"),
    ("bun_sim.py", "else poisson(rd, lam * (dep - ta))", "else poisson(rd, lam * (dep - ready))", "Fahrgäste während des Halts falsch zählen"),
    ("bun_sim.py", "tau = (1.0 + p.slack) * p.T0 / N", "tau = p.T0 / N", "Puffer des Fahrplan-Holdings streichen"),
    ("bun_sim.py", "want = ld + h_soll", "want = ld + h_soll * 0.9", "Soll-Abstand des Headway-Holdings verkürzen"),
    ("bun_sim.py", "dep = dep + (hold if hold < p.hold_max else p.hold_max)", "dep = dep + hold", "Obergrenze der Haltezeit streichen"),
    ("bun_sim.py", "if j % c == 0:", "if j % c == 1:", "Kontrollhaltestellen des Fahrplans verschieben", 0),
    ("bun_sim.py", "if j % c == 0:", "if j % c == 1:", "Kontrollhaltestellen des Headway-Holdings verschieben", 1),
    ("bun_sim.py", "free = capa - load[b]", "free = capa - load[b] + 1", "Platzgrenze lockern"),
    ("bun_sim.py", "k1 = waiting if waiting < free else free", "k1 = waiting if waiting > free else free", "Einsteigende: Maximum statt Minimum"),
    ("bun_sim.py", "ssum = t * a + (bb - a) * t * (t + 1) / (2.0 * (n + 1))", "ssum = t * a + (bb - a) * t * (t + 1) / (2.0 * n)", "erwartete Ankunftssumme des Blocks"),
    ("bun_sim.py", "wsum += t * ta - ssum", "wsum += ssum", "Wartesumme falsch"),
    ("bun_sim.py", "last_dep[j] = -best * (m + D0)", "last_dep[j] = -best * m", "Startaufstellung ohne Haltezeit"),
    ("bun_sim.py", "m = p.T0 / p.N - D0", "m = p.T0 / p.N", "Fahrzeit ohne Haltezeit"),
    ("bun_sim.py", "D0 = p.d0 + p.s * p.lam * h0", "D0 = p.d0 + p.s * p.lam", "mittlere Haltezeit ohne Soll-Takt"),
    ("bun_sim.py", "if H < half:", "if H < h0:", "Schwelle „gebündelt“"),
    ("bun_sim.py", "res[\"wait\"] = S(b_wait) / npass", "res[\"wait\"] = S(b_wait) / max(npass, 1.0) / 2.0", "Wartezeit halbieren"),
    ("bun_sim.py", "var_H = S(b_H2) / nH - mean_H * mean_H", "var_H = S(b_H2) / nH", "Varianz der Abstände ohne Mittelwert"),
    ("bun_sim.py", "return mu, math.sqrt(var / n)", "return mu, math.sqrt(var)", "Standardfehler ohne Wurzel aus n"),
    ("bun_rng.py", "LN2 = 0.6931471805599453", "LN2 = 0.69", "Konstante des Logarithmus"),
    ("bun_rng.py", "return -ln(p) * mean / k", "return -ln(p) * mean", "Erlang-Mittelwert ohne Form"),
    ("bun_rng.py", "z = z ^ (z >> np.uint64(31))", "z = z ^ (z >> np.uint64(30))", "SplitMix64: letzter Schritt"),
    ("bun_rng.py", "k += 1\n        p *= rng.uniform()", "k += 2\n        p *= rng.uniform()", "Poisson: Zähler"),
    ("bun_theory.py", "Delta = (p.B - 1) * (p.delta + p.d0 + kap * p.delta)", "Delta = p.B * (p.delta + p.d0 + kap * p.delta)", "Konvoi: Abstand des letzten Busses"),
    ("bun_theory.py", "den = 1 - p.N * kap / (1 + kap)", "den = 1 - p.N * kap", "Konvoi: Pol der Umlaufzeit"),
    ("bun_theory.py", "return hbar * (1.0 + cv * cv) / 2.0", "return hbar * (1.0 + cv) / 2.0", "Wartezeit-Paradox"),
    ("bun_theory.py", "return math.sqrt((B - 1.0) / (B + 1.0))", "return math.sqrt(B / (B + 1.0))", "CV unabhängiger Busse"),
    ("bun_theory.py", "stops_per_h = 60.0 * p.N / (p.B * h_eq)", "stops_per_h = 60.0 * p.N / (p.B * p.T0 / p.N)", "Halte je Stunde aus dem falschen Takt"),
    ("bun_constants.py", "COLLAPSE_CYCLE = 1.4 ", "COLLAPSE_CYCLE = 1.1 ", "Schwelle des Zusammenbruchs"),
    ("bun_evaluation.py", "s=s.load / (C.N_STOPS * C.LAM)", "s=s.load / C.N_STOPS", "Zustiegszeit aus der Last"),
    ("bun_evaluation.py", "if a.stat(s.strategy, \"total\")[0] > a.stat(\"none\", \"total\")[0]:", "if a.stat(s.strategy, \"total\")[0] < a.stat(\"none\", \"total\")[0]:", "Verdikt „schadet“ umkehren"),
    ("bun_evaluation.py", "xs.append((i + 1) * bin_min / 60.0)", "xs.append(i * bin_min / 60.0)", "Zeitachse des CV-Verlaufs"),
    ("bun_evaluation.py", "var = sum(b[\"H2\"][j] for b in bins for j in sl) / n - mean * mean", "var = sum(b[\"H2\"][j] for b in bins for j in sl) / n", "CV-Verlauf ohne Mittelwert"),
    ("bun_evaluation.py", "return w * 60.0 * C.WINDOW_HOURS, (w + 1) * 60.0 * C.WINDOW_HOURS", "return w * 60.0 * C.WINDOW_HOURS, w * 60.0 * C.WINDOW_HOURS + 60.0", "Fenster nur eine Stunde"),
    ("bun_evaluation.py", "return mean_se([a[\"total\"] - b[\"total\"] for a, b in zip(self.runs[strategy], self.runs[base])])", "return mean_se([a[\"total\"] - b[\"total\"] for a, b in zip(self.runs[strategy], reversed(self.runs[base]))])", "gepaarte Differenz ungepaart"),
]


def run_mutant(idx, mutant, workdir):
    fname, old, new, desc = mutant[:4]
    nth = mutant[4] if len(mutant) > 4 else None
    work = Path(workdir) / f"m{idx}"
    shutil.copytree(ROOT, work, ignore=shutil.ignore_patterns("__pycache__", ".git", "data", "venv", ".pytest_cache", "tools"))
    p = work / fname
    text = p.read_text(encoding="utf-8")
    if nth is None and text.count(old) != 1:
        return idx, desc, f"FEHLER: Stelle kommt {text.count(old)}-mal vor"
    if nth is None:
        text = text.replace(old, new)
    else:
        parts = text.split(old)
        if nth >= len(parts) - 1:
            return idx, desc, "FEHLER: Stelle zu selten"
        text = old.join(parts[:nth + 1]) + new + old.join(parts[nth + 1:])
    p.write_text(text, encoding="utf-8")
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    r = subprocess.run([sys.executable, "-B", "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *TESTS], cwd=work, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    shutil.rmtree(work, ignore_errors=True)
    return idx, desc, "gefunden" if r.returncode != 0 else "ÜBERLEBT"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    todo = [(i, m) for i, m in enumerate(MUTANTS) if a.only in m[0] or a.only in m[3]]
    with tempfile.TemporaryDirectory() as tmp, ThreadPoolExecutor(max_workers=a.jobs) as ex:
        results = list(ex.map(lambda im: run_mutant(im[0], im[1], tmp), todo))
    bad = 0
    for idx, desc, res in sorted(results):
        print(f"{idx:2d} {res:10s} {MUTANTS[idx][0]}: {desc}")
        bad += res != "gefunden"
    print(f"\n{len(results) - bad}/{len(results)} Mutanten gefunden")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
