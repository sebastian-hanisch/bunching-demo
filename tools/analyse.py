"""Auswertung der Bunching-Rohdaten (x1..x8, warm) -> auswertung.json + auswertung.txt.

Aufruf:  python -B tools/analyse.py [Rohdatenordner]
Standard: Umgebungsvariable BUN_RAW_DIR, sonst ../oepnv-planung/messreihe_bunching_ap0 (relativ zum Projekte-Ordner).

`aggregate(raw)` läuft unverändert auch über die Rohdaten der Vorab-Reihe (`oepnv-planung/messreihe_bunching`): Beide Reihen haben dieselben Schlüssel
(die Zellen tragen weiter die alte cv-Zahl), dieselbe Zeilenstruktur (key, params, seeds, m, traj) und laufen durch dieselbe Aggregation; `vergleich.py` setzt
darauf auf. Die Beschriftungen der Tabellen in auswertung.txt sind die der alten auswertung.txt (x1_cv0.4, x2_basis_schicht, x3_..., x5, x6_..., x7_..., paradox).

Statistikfelder durchgehend {n, mean, se, med, p10, p90} (je Zufalls-Seed), Anteile {k, n, p}. Zeit in Minuten, Kennzahlen je Fahrgast.
"""
import json
import math
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
DEMO = os.path.dirname(HERE)
sys.path.insert(0, DEMO)

from bun_sim import Params  # noqa: E402
from bun_sim import derived as sim_derived  # noqa: E402
import bun_theory as TH  # noqa: E402

RAW = os.environ.get("BUN_RAW_DIR") or os.path.join(DEMO, "..", "oepnv-planung", "messreihe_bunching_ap0")
NAN = float("nan")
LAM = 0.5
KAPS_TAB = (0.0, 0.0025, 0.005, 0.01, 0.015, 0.02, 0.03, 0.04)
KAPS_ALL = (0.0, 0.0025, 0.005, 0.01, 0.015, 0.02, 0.03, 0.04, 0.05, 0.06)
CVS = (0.1, 0.2, 0.4, 0.6, 0.8)
BS = (2, 3, 4, 6, 8, 12, 24)
CAPS = (0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 100.0)
KAP5 = (0.005, 0.01, 0.015, 0.02, 0.025, 0.03, 0.035, 0.04, 0.045, 0.05, 0.06, 0.07, 0.08, 0.10)
CAPA6 = (30, 40, 50, 60, 80, 120, 10 ** 9)

# Strategiezeilen der Alt-Auswertung (ohne das entfallene Überspringen)
KEYS2 = [("keine Regelung", "none"),
         ("Fahrplan c=1, Puffer 0 %", ["sched", 1, 0.0]), ("Fahrplan c=1, Puffer 5 %", ["sched", 1, 0.05]), ("Fahrplan c=1, Puffer 10 %", ["sched", 1, 0.10]),
         ("Fahrplan c=1, Puffer 15 %", ["sched", 1, 0.15]), ("Fahrplan c=3, Puffer 10 %", ["sched", 3, 0.10]),
         ("Headway c=1, η=0.8, Obergrenze 3", ["hw", 1, 0.8, 3.0]), ("Headway c=1, η=0.9, Obergrenze 3", ["hw", 1, 0.9, 3.0]),
         ("Headway c=1, η=1.0, Obergrenze 3", ["hw", 1, 1.0, 3.0]), ("Headway c=1, η=1.1, Obergrenze 3", ["hw", 1, 1.1, 3.0]),
         ("Headway c=3, η=0.9, Obergrenze 3", ["hw", 3, 0.9, 3.0]), ("Headway c=3, η=0.8, Obergrenze 1", ["hw", 3, 0.8, 1.0])]
STRAT3 = ("none", "sched1_10", "sched3_10", "sched3_05", "hw1_09", "hw1_10", "hw3_09", "hw3_10")
RULES = {
    "R1 hw c=1 eta=1.0 cap=3": ("hw", 1, 1.0, 3.0),
    "R2 hw c=3 eta=0.8 cap=2": ("hw", 3, 0.8, 2.0),
    "R3 sched c=3 slack=0.10": ("sched", 3, 0.10),
    "R4 sched c=1 slack=0.10": ("sched", 1, 0.10),
}
OBJ = {
    "total": lambda m, i: m["wait"][i] + m["ride"][i],
    "w2": lambda m, i: 2.0 * m["wait"][i] + m["ride"][i],
    "wait": lambda m, i: m["wait"][i],
}


# ------------------------------------------------------------------------------------------------ Hilfsfunktionen
def load(raw, name):
    fn = os.path.join(raw, name + ".jsonl")
    rows = []
    with open(fn, encoding="utf-8") as fh:
        for line in fh:
            rows.append(json.loads(line))
    return rows


def _ok(x):
    return x is not None and x == x


def st(xs):
    """{n, mean, se, med, p10, p90} über die gültigen Werte."""
    v = sorted(x for x in xs if _ok(x))
    n = len(v)
    if n == 0:
        return dict(n=0, mean=NAN, se=NAN, med=NAN, p10=NAN, p90=NAN)
    mu = sum(v) / n
    se = math.sqrt(sum((x - mu) ** 2 for x in v) / (n - 1) / n) if n > 1 else NAN

    def q(p):
        pos = p * (n - 1)
        lo = int(math.floor(pos))
        hi = min(lo + 1, n - 1)
        return v[lo] + (v[hi] - v[lo]) * (pos - lo)

    return dict(n=n, mean=mu, se=se, med=q(0.5), p10=q(0.1), p90=q(0.9))


def paired(a, b):
    return st([x - y for x, y in zip(a, b) if _ok(x) and _ok(y)])


def frac(k, n):
    return dict(k=k, n=n, p=(k / n if n else NAN))


def f(x, n=2):
    return ("%." + str(n) + "f") % x


def pm(t, n=2):
    return f(t["mean"], n) + " ± " + f(t["se"], n)


def win_mean(tr, key, i0, i1):
    v = [x for x in tr[key][i0:i1] if _ok(x)]
    return sum(v) / len(v) if v else None


def t_first(tr, thr):
    for i, v in enumerate(tr):
        if _ok(v) and v > thr:
            return 0.5 * (i + 1)
    return None


def P_of(**kw):
    return Params(**kw)


# ------------------------------------------------------------------------------------------------ x1
def x1(raw, A, T):
    rows = load(raw, "x1")
    d1 = {json.dumps(r["key"]): r for r in rows}
    A["x1"] = {"kcv": {}, "BN": []}
    for cv in CVS:
        A["x1"]["kcv"]["%s" % cv] = {}
        for kap in KAPS_ALL:
            r = d1[json.dumps(["kcv", cv, kap])]
            q = P_of(s=kap / LAM)
            rate = TH.growth_per_hour(q) if kap > 0 else 0.0
            tr = r["traj"]
            c7 = [t["cv"][13] for t in tr]
            tb = [t_first(t["cv"], 1.2) for t in tr]
            valid = sorted(x for x in tb if x is not None)
            med = valid[len(tb) // 2] if len(valid) > len(tb) // 2 else None
            A["x1"]["kcv"]["%s" % cv]["%s" % kap] = dict(
                kappa=kap, sigma=24 * kap, rho=24 * kap / 8, rate=rate,
                cv04=st([win_mean(t, "cv", 0, 7) for t in tr]), cv7=st(c7), share7=frac(sum(1 for x in c7 if x > 1.2), len(c7)),
                w7=st([win_mean(t, "wait", 13, 14) for t in tr]),
                cv18=st([win_mean(t, "cv", 36, 47) for t in tr]), w04=st([win_mean(t, "wait", 0, 7) for t in tr]),
                w18=st([win_mean(t, "wait", 36, 47) for t in tr]), t_med=med, reach=frac(len(valid), len(tb)),
                erlang_k=r["params"].get("erlang_k"), cv_params=r["params"].get("cv"))
    for cv in (0.4, 0.2):
        out = ["| κ = s·λ | σ = N·κ | ρ = σ/B | Wachstum je h (Theorie) | CV 0-4 h | CV 6.5-7.5 h | Seeds mit CV > 1.2 bei 7 h | CV 18-24 h | Wartezeit 0-4 h | Wartezeit 18-24 h |",
               "|---|---|---|---|---|---|---|---|---|---|"]
        for kap in KAPS_TAB:
            e = A["x1"]["kcv"]["%s" % cv]["%s" % kap]
            out.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
                f(kap, 4), f(24 * kap), f(24 * kap / 8, 3), f(e["rate"]), pm(e["cv04"]), pm(e["cv7"]), f(e["share7"]["p"]), pm(e["cv18"]), pm(e["w04"]), pm(e["w18"])))
        T["x1_cv%.1f" % cv] = "\n".join(out)
    out = ["| Variante | Fahrzeuge B | Haltestellen N | σ | Median-Zeit bis CV > 1.2 (h) | Anteil Seeds, die es in 24 h erreichen | CV 18-24 h |", "|---|---|---|---|---|---|---|"]
    lines = []
    for r in rows:
        key = r["key"]
        if key[0] == "B":
            _, B, kap = key
            N = 24
        elif key[0] == "N":
            _, N, B, sig = key
            kap = sig / N
        else:
            continue
        tr = r["traj"]
        tb = [t_first(t["cv"], 1.2) for t in tr]
        valid = sorted(x for x in tb if x is not None)
        med = valid[len(tb) // 2] if len(valid) > len(tb) // 2 else None
        c18 = st([win_mean(t, "cv", 36, 47) for t in tr])
        reach = frac(len(valid), len(tb))
        A["x1"]["BN"].append(dict(variante="B" if key[0] == "B" else "NB", B=B, N=N, sigma=N * kap, med=med, reach=reach, cv18=c18))
        lines.append(("B variiert" if key[0] == "B" else "N und B variiert", B, N, N * kap, med, reach["p"], c18))
    lines.sort(key=lambda t: (t[0], t[1], t[2], t[3]))
    for v, B, N, sg, med, rp, c18 in lines:
        out.append("| %s | %d | %d | %s | %s | %s | %s |" % (v, B, N, f(sg), f(med, 1) if med else "-", f(rp), pm(c18)))
    T["x1_BN"] = "\n".join(out)


# ------------------------------------------------------------------------------------------------ x2
def x2(raw, A, T):
    rows = load(raw, "x2")
    d2 = {json.dumps(r["key"]): r for r in rows}
    A["x2"] = {}

    def block(cond, hz, keys):
        base = d2[json.dumps([cond, hz, "none"])]["m"]
        head = ["| Strategie | Wartezeit | Fahrzeit im Bus | Gesamt | CV der Abstände | Anteil Wartezeit > 1.5 h_soll | Anteil gebündelt | Umlaufzeit min | Halt je Haltestelle min | Gesamt gegenüber ohne (gepaart) |",
                "|---|---|---|---|---|---|---|---|---|---|"]
        res = {}
        for label, k in keys:
            r = d2[json.dumps([cond, hz, k])]["m"]
            tot = r["total"]
            dd = paired(tot, base["total"])
            e = dict(wait=st(r["wait"]), ride=st(r["ride"]), total=st(tot), cv=st(r["cv"]), long=st(r["long"]), bunch=st(r["bunch"]), cycle=st(r["cycle"]),
                     hold=st(r["hold"]), d_total=dd, hbar=st(r["hbar"]))
            res[label] = e
            head.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
                label, pm(e["wait"]), f(e["ride"]["mean"]), f(e["total"]["mean"]), f(e["cv"]["mean"]), f(e["long"]["mean"], 3), f(e["bunch"]["mean"], 3),
                f(e["cycle"]["mean"], 1), f(e["hold"]["mean"]), pm(dd)))
        return "\n".join(head), res

    for hz in ("schicht", "stat"):
        T["x2_basis_" + hz], A["x2"]["basis/" + hz] = block("basis", hz, KEYS2)
    for cond in ("cv0.2", "cv0.6", "kap0.01", "kap0.03"):
        T["x2_%s_schicht" % cond], A["x2"]["%s/schicht" % cond] = block(cond, "schicht", [KEYS2[0], KEYS2[3], KEYS2[8], KEYS2[10]])
    # Wartezeit-Paradox
    head = ["| Strategie | gemessene Wartezeit | h̄ (1 + CV²) / 2 | Verhältnis |", "|---|---|---|---|"]
    A["paradox"] = []
    for label, k in [KEYS2[0], KEYS2[3], KEYS2[8]]:
        m = d2[json.dumps(["basis", "schicht", k])]["m"]
        pred = st([h * (1 + c * c) / 2 for h, c in zip(m["hbar"], m["cv"])])
        w = st(m["wait"])
        ratio = st([a / (h * (1 + c * c) / 2) for a, h, c in zip(m["wait"], m["hbar"], m["cv"])])
        head.append("| %s | %s | %s | %s |" % (label, pm(w), pm(pred), f(w["mean"] / pred["mean"])))
        A["paradox"].append(dict(label=label, wait=w, pred=pred, ratio=ratio, ratio_means=w["mean"] / pred["mean"]))
    T["paradox"] = "\n".join(head)


# ------------------------------------------------------------------------------------------------ x3
def b_eq(pts, target):
    pts = sorted(pts)
    for (b1, w1), (b2, w2) in zip(pts, pts[1:]):
        if w2 <= target <= w1:
            t = (math.log(w1) - math.log(target)) / (math.log(w1) - math.log(w2))
            return math.exp(math.log(b1) + t * (math.log(b2) - math.log(b1)))
    return None


def x3(raw, A, T):
    rows = load(raw, "x3")
    d3 = {(r["key"][0], r["key"][1], r["key"][2], r["key"][3]): r for r in rows}
    A["x3"] = {}
    for cond in ("basis", "cv0.6", "kap0.03"):
        for hz in ("schicht", "stat"):
            blk = {}
            for B in BS:
                for sn in STRAT3:
                    m = d3[(cond, hz, B, sn)]["m"]
                    blk["%d/%s" % (B, sn)] = dict(wait=st(m["wait"]), total=st(m["total"]), cv=st(m["cv"]), cycle=st(m["cycle"]))
            A["x3"]["%s/%s" % (cond, hz)] = blk
            for metric in ("wait", "total"):
                head = ["| B | Soll-Takt h0 min | ohne Regelung | Fahrplan c=1 / 10 % | Fahrplan c=3 / 5 % | Headway c=1, η=1.0 | Headway c=3, η=1.0 |", "|---|---|---|---|---|---|---|"]
                for B in BS:
                    cells = [f(blk["%d/%s" % (B, sn)][metric]["mean"]) for sn in ("none", "sched1_10", "sched3_05", "hw1_10", "hw3_10")]
                    head.append("| %d | %s | %s |" % (B, f(60.0 / B, 1), " | ".join(cells)))
                T["x3_%s_%s_%s" % (cond, hz, metric)] = "\n".join(head)
    A["b_eq"] = {}
    for cond in ("basis", "cv0.6", "kap0.03"):
        pts = [(B, st(d3[(cond, "schicht", B, "none")]["m"]["wait"])["mean"]) for B in BS]
        for sn in ("sched1_10", "hw1_10"):
            w = st(d3[(cond, "schicht", 8, sn)]["m"]["wait"])["mean"]
            A["b_eq"]["%s/%s" % (cond, sn)] = dict(wait=w, B_eq=b_eq(pts, w))


# ------------------------------------------------------------------------------------------------ x4 / x7
def _key(k):
    return tuple(k)


def x4(raw, A, T):
    rows = load(raw, "x4")
    A["x4"] = {}
    for cond in ("basis", "hart"):
        for oname, J in OBJ.items():
            data = {}
            for r in rows:
                k = r["key"]
                if k[0] != cond:
                    continue
                fam = k[2]
                sub = tuple(k[3:]) if fam != "none" else ()
                data[(k[1], fam) + sub] = [J(r["m"], i) for i in range(len(r["seeds"]))]
            none_tr, none_te = data[("train", "none")], data[("test", "none")]
            cells = sorted({k[1:] for k in data if k[0] == "train" and k[1] != "none"}, key=str)
            mean = lambda v: sum(v) / len(v)  # noqa: E731
            best = {}
            for fam in ("hw", "sched", "all"):
                bk, bv = None, 1e18
                for key in cells:
                    if fam != "all" and key[0] != fam:
                        continue
                    v = mean(data[("train",) + key])
                    if v < bv:
                        bv, bk = v, key
                best[fam] = (bk, bv)
            mean_none_te = mean(none_te)
            te_all = {key: mean(data[("test",) + key]) for key in cells}
            opt_te_key = min(te_all, key=te_all.get)
            opt_te = te_all[opt_te_key]
            res = {}
            for fam, (bk, bv) in best.items():
                te = data[("test",) + bk]
                res[fam] = dict(key=list(bk), train=bv, test=st(te))
            opt_all_te = data[("test",) + best["all"][0]]
            rr = {}
            for name, rk in RULES.items():
                te = data[("test",) + rk]
                dif = paired(te, opt_all_te)
                gain = (mean_none_te - mean(te)) / (mean_none_te - mean(opt_all_te))
                rr[name] = dict(test=st(te), luecke=dif, gewinnanteil=gain)
            wid = {}
            for fam in ("hw", "sched"):
                vals = [v for key, v in te_all.items() if key[0] == fam]
                for tol in (0.01, 0.02, 0.05, 0.10):
                    wid["%s_%.0f%%" % (fam, tol * 100)] = dict(k=sum(1 for v in vals if v <= opt_te * (1 + tol)), n=len(vals))
            worse = sum(1 for v in te_all.values() if v > mean_none_te)
            ent = dict(none_test=st(none_te), none_train=st(none_tr), opt=res, opt_testseeds=dict(key=list(opt_te_key), value=opt_te), regeln=rr, breite=wid,
                       schlechter_als_nichts=dict(k=worse, n=len(te_all)))
            if cond == "basis" and oname == "total":
                # Fläche Fahrplan c x Puffer auf den Test-Seeds, Gesamtreisezeit
                fl = {}
                for c in (1, 2, 3, 4, 6, 8, 12):
                    fl["%d" % c] = {"%s" % sl: st(data[("test", "sched", c, sl)]) for sl in (0.0, 0.025, 0.05, 0.075, 0.10, 0.125, 0.15, 0.20, 0.30)}
                ent["flaeche_sched_test"] = fl
                # Wirkung der Obergrenze (Trainings-Seeds)
                knob = {}
                for c in (1, 3):
                    for eta in (0.7, 0.9, 1.0, 1.2):
                        vals = [st(data[("train", "hw", c, eta, cap)]) for cap in CAPS]
                        knob["c%d_eta%.1f" % (c, eta)] = vals
                ent["cap_wirkung"] = knob
                ent["c_wirkung"] = {"%d" % c: dict(total=st(data[("train", "hw", c, 1.0, 3.0)])) for c in (1, 2, 3, 4, 6, 8, 12)}
            A["x4"]["%s/%s" % (cond, oname)] = ent


def x7(raw, A, T):
    rows = load(raw, "x7")
    A["x7"] = {}
    for oname, J in OBJ.items():
        head = ["| B | ohne Regelung | bestes Headway-Holding (Training) | Test | bestes Fahrplan-Holding (Training) | Test | Headway − Fahrplan (gepaart) | Regel Headway c=1, η=1.0 | Regel Fahrplan c=1, 10 % |",
                "|---|---|---|---|---|---|---|---|---|"]
        for B in (2, 3, 4, 6, 8, 12):
            data = {}
            for r in rows:
                k = r["key"]
                if k[0] == B:
                    data[(k[1],) + tuple(k[2:])] = [J(r["m"], i) for i in range(len(r["seeds"]))]
            mean = lambda v: sum(v) / len(v)  # noqa: E731
            best = {}
            for fam in ("hw", "sched"):
                cand = [k for k in data if k[0] == "train" and k[1] == fam]
                bk = min(cand, key=lambda k: mean(data[k]))
                best[fam] = (bk[1:], data[("test",) + bk[1:]])
            dd = paired(best["hw"][1], best["sched"][1])
            r1 = data[("test", "hw", 1, 1.0, 3.0)]
            r4 = data[("test", "sched", 1, 0.1)]
            head.append("| %d | %s | %s | %s | %s | %s | %s | %s | %s |" % (
                B, f(mean(data[("test", "none")])), str(tuple(best["hw"][0][1:])), f(mean(best["hw"][1])), str(tuple(best["sched"][0][1:])), f(mean(best["sched"][1])), pm(dd),
                f(mean(r1)), f(mean(r4))))
            A["x7"]["%s/%d" % (oname, B)] = dict(none=st(data[("test", "none")]), hw=st(best["hw"][1]), hw_key=list(best["hw"][0][1:]), sched=st(best["sched"][1]),
                                                  sched_key=list(best["sched"][0][1:]), diff=dd, R1=st(r1), R4=st(r4))
        T["x7_" + oname] = "\n".join(head)


# ------------------------------------------------------------------------------------------------ x5
def x5(raw, A, T):
    rows = load(raw, "x5")
    d5 = {tuple(r["key"][1:]): r for r in rows}
    head = ["| σ = N·s·λ | ρ = σ/B | Umlaufzeit ohne Regelung | dichter Konvoi (Formel) | Verhältnis | Wartezeit ohne | Headway c=1, η=1.0 | Fahrplan c=1 / 10 % | Fahrplan c=1 / 20 % |",
            "|---|---|---|---|---|---|---|---|---|"]
    A["x5"] = []
    for kap in KAP5:
        q = P_of(s=kap / LAM)
        tc = TH.convoy_cycle(q)
        cyc = st(d5[(8, kap, "none")]["m"]["cycle"])
        w = {sn: st(d5[(8, kap, sn)]["m"]["wait"]) for sn in ("none", "hw1_10", "sched1_10", "sched1_20")}
        cm = cyc["mean"]
        ratio = (cm / tc) if (tc < 1e5 and cm == cm) else None
        head.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            f(24 * kap), f(24 * kap / 8, 3), (f(cm, 0) if cm == cm else "-"), (f(tc, 0) if tc < 1e5 else "∞"), (f(ratio) if ratio is not None else "-"),
            f(w["none"]["mean"], 1), f(w["hw1_10"]["mean"], 1), f(w["sched1_10"]["mean"], 1), f(w["sched1_20"]["mean"], 1)))
        A["x5"].append(dict(kappa=kap, sigma=24 * kap, cycle=cyc, convoy=(tc if tc < 1e5 else "inf"), ratio=ratio,
                            wait=w, wait_hw09=st(d5[(8, kap, "hw1_09")]["m"]["wait"])))
    T["x5"] = "\n".join(head)
    head = ["| σ | B=4: ohne | B=4: Headway | B=8: ohne | B=8: Headway | B=12: ohne | B=12: Headway |", "|---|---|---|---|---|---|---|"]
    A["x5_B"] = []
    for kap in (0.01, 0.02, 0.03, 0.04, 0.045, 0.05, 0.06, 0.07):
        e = {"B%d/%s" % (B, sn): st(d5[(B, kap, sn)]["m"]["wait"]) for B in (4, 8, 12) for sn in ("none", "hw1_10")}
        head.append("| %s | " % f(24 * kap) + " | ".join(f(e["B%d/%s" % (B, sn)]["mean"], 1) for B in (4, 8, 12) for sn in ("none", "hw1_10")) + " |")
        A["x5_B"].append(dict(kappa=kap, sigma=24 * kap, wait=e))
    T["x5_B"] = "\n".join(head)


# ------------------------------------------------------------------------------------------------ x6
def x6(raw, A, T):
    rows = load(raw, "x6")
    d6 = {tuple(r["key"][1:]): r for r in rows}
    P = Params()
    A["x6"] = {}
    for kap in (0.02, 0.03, 0.04):
        for hz in ("schicht", "stat"):
            head = ["| Kapazität | mittlere Besetzung / Kapazität | ohne Regelung: Wartezeit, CV | Fahrplan c=1 / 10 %: Wartezeit, CV | Headway c=1, η=1.0: Wartezeit, CV | Umlaufzeit min: ohne / Fahrplan / Headway |",
                    "|---|---|---|---|---|---|"]
            blk = {}
            for capa in CAPA6:
                r = {sn: d6[(kap, capa, hz, sn)]["m"] for sn in ("none", "sched1_10", "hw1_10")}
                load_ = P.N * P.lam * st(r["hw1_10"]["ride"])["mean"] / P.B
                occ = load_ / capa if capa < 10 ** 8 else 0.0
                e = {sn: dict(wait=st(r[sn]["wait"]), cv=st(r[sn]["cv"]), cycle=st(r[sn]["cycle"]), total=st(r[sn]["total"]),
                              fullshare=st(r[sn].get("fullshare", [None]))) for sn in r}
                e["occ"] = occ
                blk["%d" % capa] = e
                head.append("| %s | %s | %s, %s | %s, %s | %s, %s | %s / %s / %s |" % (
                    "unbegrenzt" if capa >= 10 ** 8 else capa, f(occ) if capa < 10 ** 8 else "-",
                    f(e["none"]["wait"]["mean"], 1), f(e["none"]["cv"]["mean"]), f(e["sched1_10"]["wait"]["mean"], 1), f(e["sched1_10"]["cv"]["mean"]),
                    f(e["hw1_10"]["wait"]["mean"], 1), f(e["hw1_10"]["cv"]["mean"]), f(e["none"]["cycle"]["mean"], 0), f(e["sched1_10"]["cycle"]["mean"], 0),
                    f(e["hw1_10"]["cycle"]["mean"], 0)))
            A["x6"]["%s/%s" % (kap, hz)] = blk
            if kap in (0.02, 0.04):
                T["x6_%s_%s" % (kap, hz)] = "\n".join(head)


# ------------------------------------------------------------------------------------------------ x8
def x8(raw, A, T):
    rows = load(raw, "x8")
    d = {tuple(r["key"]): r for r in rows}
    A["x8"] = {}
    for (vn, hz, sn), r in d.items():
        m = r["m"]
        A["x8"]["%s/%s" % (vn, sn)] = dict(wait=st(m["wait"]), cv=st(m["cv"]), cycle=st(m["cycle"]), total=st(m["total"]))


# ------------------------------------------------------------------------------------------------ warm
def warm(raw, A, T):
    rows = load(raw, "warm")
    A["warm"] = {}
    A["verlauf"] = {}
    for r in rows:
        sn = r["key"][2]
        tr = r["traj"]
        n = len(tr[0]["wait"])
        w = [st([t["wait"][i] for t in tr])["mean"] for i in range(n)]
        c = [st([t["cv"][i] for t in tr])["mean"] for i in range(n)]
        late_mean = sum(w[28:46]) / len(w[28:46])

        def settle(tol):
            for i in range(n):
                if all(abs(x - late_mean) <= tol * late_mean for x in w[i:]):
                    return 0.5 * (i + 1)
            return None

        def per_seed(fn):
            return st([fn(t) for t in tr])

        mean_ = lambda xs: sum(xs) / len(xs)  # noqa: E731
        full = per_seed(lambda t: mean_(t["wait"][0:19]))
        cut = per_seed(lambda t: mean_(t["wait"][4:19]))
        A["warm"][sn] = dict(
            wait_h1=per_seed(lambda t: t["wait"][0]), wait_h2=per_seed(lambda t: t["wait"][2]), wait_h4=per_seed(lambda t: t["wait"][6]),
            wait_h8=per_seed(lambda t: t["wait"][14]), wait_h12=per_seed(lambda t: t["wait"][22]), wait_late=per_seed(lambda t: mean_(t["wait"][28:46])),
            cv_h1=per_seed(lambda t: t["cv"][0]), cv_h4=per_seed(lambda t: t["cv"][6]), cv_h12=per_seed(lambda t: t["cv"][22]),
            settle5=settle(0.05), settle10=settle(0.10), mittel_0_10h=full, mittel_2_10h=cut,
            verzerrung=1.0 - full["mean"] / cut["mean"])
        # Verlauf in 1-h-Schritten (Fenster i = 0, 2, 4, ... decken [0,1], [1,2], ...): Mittelkurve über die Seeds
        A["verlauf"][sn] = dict(stunde=[0.5 * (i + 1) for i in range(0, n, 2)], cv=[c[i] for i in range(0, n, 2)], wait=[w[i] for i in range(0, n, 2)])


# ------------------------------------------------------------------------------------------------ Modell, Prüfungen
def modell(A):
    p = Params()
    h0, D0, m = sim_derived(p)
    kap = p.s * p.lam
    heq, Deq, weq = TH.equilibrium(p)
    A["modell"] = dict(N=p.N, B=p.B, T0=p.T0, d0=p.d0, s=p.s, lam=p.lam, delta=p.delta, h0=h0, m=m, D0=D0, kappa=kap, sigma=p.sigma, rho=p.sigma / p.B,
                       h_eq=heq, D_eq=Deq, wait_eq=weq, growth_per_hour=TH.growth_per_hour(p), convoy_cycle=TH.convoy_cycle(p),
                       erlang_k=p.erlang_k, cv_erlang=1 / math.sqrt(p.erlang_k))


def pruef(raw, A):
    for nm in ("orakel", "rng", "erhaltung", "determinismus", "nullspalten", "timing", "wirkungslos"):
        fn = os.path.join(raw, "pruefungen_%s.json" % nm)
        if os.path.exists(fn):
            with open(fn, encoding="utf-8") as fh:
                A["pr_" + nm] = json.load(fh)
    if "pr_timing" in A:
        A["rechenzeit"] = A["pr_timing"]


def aggregate(raw, with_pruefungen=True):
    A, T = {}, {}
    modell(A)
    x1(raw, A, T)
    x2(raw, A, T)
    x3(raw, A, T)
    x4(raw, A, T)
    x5(raw, A, T)
    x6(raw, A, T)
    x7(raw, A, T)
    x8(raw, A, T)
    warm(raw, A, T)
    if with_pruefungen:
        pruef(raw, A)
    A["tabellen"] = T
    return A, T


def main(raw=RAW):
    A, T = aggregate(raw)
    A["meta"] = dict(seeds="1-30 (Parametersuche: Training 1-30, Test 101-160)", fenster="Schicht 10 h mit 2 h Einschwingzeit, stationär 40 h mit 10 h, Verlauf 24 h",
                     ersatz="Gamma-Störung (cv 0,1 / 0,2 / 0,4 / 0,6 / 0,8) -> Erlang k = 100 / 25 / 6 / 3 / 2 (Variationskoeffizient 0,100 / 0,200 / 0,408 / 0,577 / 0,707)")
    with open(os.path.join(raw, "auswertung.json"), "w", encoding="utf-8") as fh:
        json.dump(A, fh, indent=1, ensure_ascii=False, default=str)
    notes = {"x1_cv0.4": "Hinweis: Störung Erlang k = 6 (Variationskoeffizient 0.408; Vorab Gamma cv 0.4)", "x1_cv0.2": "Hinweis: Störung Erlang k = 25 (Variationskoeffizient 0.200; Vorab Gamma cv 0.2)",
             "x2_cv0.2_schicht": "Hinweis: Erlang k = 25", "x2_cv0.6_schicht": "Hinweis: Erlang k = 3 (Variationskoeffizient 0.577; Vorab Gamma cv 0.6)"}
    with open(os.path.join(raw, "auswertung.txt"), "w", encoding="utf-8") as fh:
        for k, v in T.items():
            fh.write("### %s\n%s%s\n\n" % (k, (notes[k] + "\n") if k in notes else "", v))
    print("fertig; Tabellen:", len(T), "->", os.path.join(raw, "auswertung.txt"))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else RAW)
