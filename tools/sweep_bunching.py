"""Bunching-Sweeps (Port der Vorab-Messreihe `oepnv-planung/messreihe_bunching/run_x*.py` auf den neuen Kern der Demo: SplitMix64, Erlang-Störung).

Gleiche Zellen und Zufalls-Seeds wie die Vorab-Reihe (Seeds 1-30, Parametersuche Training 1-30 / Test 101-160, Messfenster 10 h mit 2 h Einschwingzeit bzw. 40 h mit
10 h, Verlaufsläufe 24 h). Die Gamma-Störung mit Variationskoeffizient cv ist durch Erlang mit Form k ersetzt: cv 0,1 / 0,2 / 0,4 / 0,6 / 0,8 -> k = 100 / 25 / 6 / 3 / 2
(Variationskoeffizient 1/sqrt(k) = 0,100 / 0,200 / 0,408 / 0,577 / 0,707). Die Schlüssel der Zellen tragen weiter die alte cv-Zahl, damit Alt und Neu durch
dieselbe Auswertung laufen. Das Überspringen entfällt (Kern kennt es nicht). Kapazität und Wartebuchhaltung sind im Kern eine einzige Simulation.

Rohdaten (eine JSON-Zeile je Zelle: key, params, seeds, m = Kennzahlen je Zufalls-Seed, traj = Verlaufskurven, sec = Rechenzeit der Zelle):
    x1.jsonl  Entstehung des Pulks ohne Regelung (24 h, Verlauf): kappa x cv, B, N/B
    x2.jsonl  Strategien im Standardfall + Zusatzbedingungen, 10 h und 40 h
    x3.jsonl  Zahl der Busse B bei T0 = 60
    x4.jsonl  Gitter Regel gegen Optimum (Training 1-30, Test 101-160)
    x5.jsonl  Lastachse sigma (Zusammenbruch), 40 h
    x6.jsonl  Fahrzeugkapazität
    x7.jsonl  Optimum je Familie und Busanzahl (Headway gegen Fahrplan)
    x8.jsonl  Sensitivität (Mindestabstand, Grundhalt, N/B, T0)
    warm.jsonl  Einschwingzeit (Verlauf 24 h, fünf Strategien)

Aufruf:  python -B tools/sweep_bunching.py [Ausgabeordner|-] [Prozesse (höchstens 4)] [Teile: alle | x1,x3,... | probe]
Standard: Umgebungsvariable BUN_RAW_DIR, sonst ../oepnv-planung/messreihe_bunching_ap0 (relativ zum Projekte-Ordner), 4 Prozesse, alle Teile.
"""
import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import json  # noqa: E402
import math  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from multiprocessing import Pool  # noqa: E402

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
DEMO = os.path.dirname(HERE)
sys.path.insert(0, DEMO)

from bun_sim import INF, Params, simulate  # noqa: E402

OUT_DIR = os.environ.get("BUN_RAW_DIR") or os.path.join(DEMO, "..", "oepnv-planung", "messreihe_bunching_ap0")
KMAP = {0.1: 100, 0.2: 25, 0.4: 6, 0.6: 3, 0.8: 2}          # alte cv -> Erlang-Form k
KEYS = ("wait", "long", "ride", "total", "cv", "bunch", "cycle", "hold", "fullshare", "npass", "hbar", "maxload")
SEEDS = list(range(1, 31))
TRAIN = list(range(1, 31))
TEST = list(range(101, 161))
SHORT = (10 * 60.0, 2 * 60.0)       # Schicht: 10 h, Einschwingzeit 2 h
LONG = (40 * 60.0, 10 * 60.0)       # stationär: 40 h, Einschwingzeit 10 h
DAY = 24 * 60.0
LAM = 0.5
PARTS = ("x1", "x2", "x3", "x4", "x5", "x6", "x7", "x8", "warm")


def traj_from_bins(b):
    """Gleitende 1-h-Fenster (zwei Bins) im Abstand von 30 min: CV der Abfahrtsabstände, Wartezeit, Anteil gebündelt (wie die Vorab-Reihe)."""
    n = len(b["Hn"])
    out = dict(cv=[], wait=[], bunch=[], long=[], ride=[], hold=[])
    for i in range(0, n - 1):
        nH = b["Hn"][i] + b["Hn"][i + 1]
        npass = b["pass_"][i] + b["pass_"][i + 1]
        if nH == 0:
            out["cv"].append(None)
            out["bunch"].append(None)
            out["hold"].append(None)
        else:
            mu = (b["H"][i] + b["H"][i + 1]) / nH
            var = (b["H2"][i] + b["H2"][i + 1]) / nH - mu * mu
            out["cv"].append(math.sqrt(max(var, 0.0)) / mu)
            out["bunch"].append((b["bunch"][i] + b["bunch"][i + 1]) / nH)
            out["hold"].append((b["hold"][i] + b["hold"][i + 1]) / nH)
        if npass > 0:
            out["wait"].append((b["wait"][i] + b["wait"][i + 1]) / npass)
            out["long"].append((b["long"][i] + b["long"][i + 1]) / npass)
        else:
            out["wait"].append(None)
            out["long"].append(None)
        al = b["alight"][i] + b["alight"][i + 1]
        out["ride"].append((b["ride"][i] + b["ride"][i + 1]) / al if al > 0 else None)
    return out


def jsonable(o):
    if isinstance(o, dict):
        return {k: jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    if isinstance(o, float) and math.isinf(o):
        return "inf" if o > 0 else "-inf"
    return o


def work(args):
    fname, key, params, seeds, traj = args
    t0 = time.perf_counter()
    res = {k: [] for k in KEYS}
    trs = []
    for sd in seeds:
        q = dict(params)
        if traj:
            q["bins"] = True
            q["T_warm"] = 0.0
        r = simulate(Params(**q), sd)
        for k in KEYS:
            v = r[k]
            res[k].append(None if v != v else v)
        if traj:
            trs.append(traj_from_bins(r["bins"]))
    out = dict(key=key, params=jsonable(params), seeds=list(seeds), m=res, sec=time.perf_counter() - t0)
    if traj:
        out["traj"] = trs
    return fname, out


def cost(c):
    fname, key, p, seeds, traj = c
    B, N, T0 = p.get("B", 8), p.get("N", 24), p.get("T0", 60.0)
    w = 3.0 if p.get("capa", INF) != INF else 1.0
    return len(seeds) * p.get("T_end", 600.0) * N * (B + 8) / T0 * w


def cells_x1():
    cs = []
    for cv in (0.1, 0.2, 0.4, 0.6, 0.8):
        for kap in (0.0, 0.0025, 0.005, 0.01, 0.015, 0.02, 0.03, 0.04, 0.05, 0.06):
            cs.append(("x1", ["kcv", cv, kap], dict(erlang_k=KMAP[cv], s=kap / LAM, T_end=DAY, T_warm=0.0, strat="none"), SEEDS, True))
    for B in (3, 4, 6, 8, 12, 24):
        for kap in (0.01, 0.02):
            cs.append(("x1", ["B", B, kap], dict(B=B, s=kap / LAM, T_end=DAY, T_warm=0.0, strat="none"), SEEDS, True))
    for N, B in ((12, 4), (24, 8), (30, 10), (36, 12)):
        for sig in (0.24, 0.48):
            cs.append(("x1", ["N", N, B, sig], dict(N=N, B=B, s=(sig / N) / LAM, T_end=DAY, T_warm=0.0, strat="none"), SEEDS, True))
    return cs


def strategies_x2():
    yield "none", dict(strat="none")
    for c in (1, 3, 6):
        for sl in (0.0, 0.05, 0.10, 0.15):
            yield ["sched", c, sl], dict(strat="sched", c=c, slack=sl)
    for c in (1, 3):
        for eta in (0.6, 0.8, 0.9, 1.0, 1.1):
            for cap in (1.0, 3.0, 100.0):
                yield ["hw", c, eta, cap], dict(strat="hw", c=c, eta=eta, hold_max=cap)


def cells_x2():
    conds = {"basis": dict(), "cv0.2": dict(erlang_k=KMAP[0.2]), "cv0.6": dict(erlang_k=KMAP[0.6]), "kap0.01": dict(s=0.02), "kap0.03": dict(s=0.06)}
    cs = []
    for cn, cd in conds.items():
        for hz, (te, tw) in {"schicht": SHORT, "stat": LONG}.items():
            for sk, sd in strategies_x2():
                cs.append(("x2", [cn, hz, sk], dict(T_end=te, T_warm=tw, **cd, **sd), SEEDS, False))
    return cs


def cells_x3():
    strat = {
        "none": dict(strat="none"),
        "sched1_10": dict(strat="sched", c=1, slack=0.10),
        "sched3_10": dict(strat="sched", c=3, slack=0.10),
        "sched3_05": dict(strat="sched", c=3, slack=0.05),
        "hw1_09": dict(strat="hw", c=1, eta=0.9, hold_max=3.0),
        "hw1_10": dict(strat="hw", c=1, eta=1.0, hold_max=3.0),
        "hw3_09": dict(strat="hw", c=3, eta=0.9, hold_max=3.0),
        "hw3_10": dict(strat="hw", c=3, eta=1.0, hold_max=3.0),
    }
    conds = {"basis": dict(), "kap0.03": dict(s=0.06), "cv0.6": dict(erlang_k=KMAP[0.6])}
    cs = []
    for cn, cd in conds.items():
        for hz, (te, tw) in {"schicht": SHORT, "stat": LONG}.items():
            for B in (2, 3, 4, 6, 8, 12, 24):
                for sn, sd in strat.items():
                    cs.append(("x3", [cn, hz, B, sn], dict(B=B, T_end=te, T_warm=tw, **cd, **sd), SEEDS, False))
    return cs


def cells_x4():
    conds = {"basis": dict(), "hart": dict(erlang_k=KMAP[0.6], s=0.06)}
    cs = []
    for cn, cd in conds.items():
        base = dict(T_end=SHORT[0], T_warm=SHORT[1], **cd)
        for sd_name, sds in (("train", TRAIN), ("test", TEST)):
            cs.append(("x4", [cn, sd_name, "none"], dict(base, strat="none"), sds, False))
            for c in (1, 2, 3, 4, 6, 8, 12):
                for eta in (0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3):
                    for cap in (0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 100.0):
                        cs.append(("x4", [cn, sd_name, "hw", c, eta, cap], dict(base, strat="hw", c=c, eta=eta, hold_max=cap), sds, False))
                for sl in (0.0, 0.025, 0.05, 0.075, 0.10, 0.125, 0.15, 0.20, 0.30):
                    cs.append(("x4", [cn, sd_name, "sched", c, sl], dict(base, strat="sched", c=c, slack=sl), sds, False))
    return cs


def cells_x5():
    strat = {"none": dict(strat="none"), "sched1_10": dict(strat="sched", c=1, slack=0.10), "sched1_20": dict(strat="sched", c=1, slack=0.20),
             "hw1_10": dict(strat="hw", c=1, eta=1.0, hold_max=3.0), "hw1_09": dict(strat="hw", c=1, eta=0.9, hold_max=3.0)}
    cs = []
    for B in (4, 8, 12):
        for kap in (0.005, 0.01, 0.015, 0.02, 0.025, 0.03, 0.035, 0.04, 0.045, 0.05, 0.06, 0.07, 0.08, 0.10):
            for sn, sd in strat.items():
                if B != 8 and sn not in ("none", "hw1_10"):
                    continue
                cs.append(("x5", ["sig", B, kap, sn], dict(B=B, s=kap / LAM, T_end=LONG[0], T_warm=LONG[1], **sd), SEEDS, False))
    return cs


def cells_x6():
    strat = {"none": dict(strat="none"), "sched1_10": dict(strat="sched", c=1, slack=0.10), "hw1_10": dict(strat="hw", c=1, eta=1.0, hold_max=3.0)}
    cs = []
    for kap in (0.02, 0.03, 0.04):
        for capa in (30, 40, 50, 60, 80, 120, 10 ** 9):
            for hz, (te, tw) in {"schicht": SHORT, "stat": LONG}.items():
                for sn, sd in strat.items():
                    cs.append(("x6", ["cap", kap, capa, hz, sn], dict(s=kap / LAM, T_end=te, T_warm=tw, capa=(INF if capa >= 10 ** 9 else int(capa)), **sd), SEEDS, False))
    return cs


def cells_x7():
    cs = []
    for B in (2, 3, 4, 6, 8, 12):
        base = dict(B=B, T_end=SHORT[0], T_warm=SHORT[1])
        for nm, sds in (("train", TRAIN), ("test", TEST)):
            cs.append(("x7", [B, nm, "none"], dict(base, strat="none"), sds, False))
            for c in (1, 2, 3, 4, 6):
                for eta in (0.7, 0.8, 0.9, 1.0, 1.1, 1.2):
                    for cap in (1.0, 3.0, 100.0):
                        cs.append(("x7", [B, nm, "hw", c, eta, cap], dict(base, strat="hw", c=c, eta=eta, hold_max=cap), sds, False))
                for sl in (0.0, 0.025, 0.05, 0.075, 0.10, 0.125, 0.15, 0.20, 0.30):
                    cs.append(("x7", [B, nm, "sched", c, sl], dict(base, strat="sched", c=c, slack=sl), sds, False))
    return cs


def cells_x8():
    strat = {"none": dict(strat="none"), "sched1_10": dict(strat="sched", c=1, slack=0.10), "hw1_10": dict(strat="hw", c=1, eta=1.0, hold_max=3.0)}
    var = {"basis": {}, "delta0": dict(delta=0.0), "delta0.25": dict(delta=0.25), "delta0.5": dict(delta=0.5), "d0=0.1": dict(d0=0.1), "d0=0.5": dict(d0=0.5),
           "N12": dict(N=12), "N30_B10": dict(N=30, B=10), "T0=90": dict(T0=90.0), "T0=40": dict(T0=40.0)}
    cs = []
    for vn, vd in var.items():
        for sn, sd in strat.items():
            cs.append(("x8", [vn, "schicht", sn], dict(T_end=SHORT[0], T_warm=SHORT[1], **vd, **sd), SEEDS, False))
    return cs


def cells_warm():
    strat = {"none": dict(strat="none"), "sched1_10": dict(strat="sched", c=1, slack=0.10), "hw1_10": dict(strat="hw", c=1, eta=1.0, hold_max=3.0),
             "hw1_08": dict(strat="hw", c=1, eta=0.8, hold_max=3.0), "sched3_05": dict(strat="sched", c=3, slack=0.05)}
    return [("warm", ["warm", 0.02, sn], dict(s=0.02 / LAM, T_end=DAY, T_warm=0.0, **sd), SEEDS, True) for sn, sd in strat.items()]


BUILD = {"x1": cells_x1, "x2": cells_x2, "x3": cells_x3, "x4": cells_x4, "x5": cells_x5, "x6": cells_x6, "x7": cells_x7, "x8": cells_x8, "warm": cells_warm}


def main(out_dir, procs, parts, probe=False):
    procs = max(1, min(4, int(procs)))
    os.makedirs(out_dir, exist_ok=True)
    cells = []
    for p in parts:
        cs = BUILD[p]()
        if probe:
            cs = sorted(cs, key=cost, reverse=True)[:4]
            cs = [(f, k, q, s[:2], t) for f, k, q, s, t in cs]
        cells += cs
    cells.sort(key=cost, reverse=True)                      # teure Aufträge zuerst
    total_cost = sum(cost(c) for c in cells)
    print("%d Zellen (%s), %d Prozesse, Ausgabe %s" % (len(cells), ",".join(parts), procs, os.path.abspath(out_dir)), flush=True)
    files = {}
    for p in parts:
        files[p] = open(os.path.join(out_dir, p + ".jsonl"), "w", encoding="utf-8")
    t0 = time.time()
    done_cost = 0.0
    cost_of = {id(c): cost(c) for c in cells}
    n_done = 0
    secs = {}
    try:
        with Pool(procs) as pool:
            for (fname, r), c in zip(pool.imap(work, cells, chunksize=1), cells):
                files[fname].write(json.dumps(r, ensure_ascii=False) + "\n")
                secs[fname] = secs.get(fname, 0.0) + r["sec"]
                n_done += 1
                done_cost += cost_of[id(c)]
                if n_done % 100 == 0 or n_done == len(cells):
                    el = time.time() - t0
                    print("  %d/%d Zellen, %.0f s, geschätzt noch %.0f s" % (n_done, len(cells), el, el * (total_cost - done_cost) / max(done_cost, 1e-9)), flush=True)
    finally:
        for f in files.values():
            f.close()
    wall = time.time() - t0
    print("fertig: %d Zellen, %.0f s Wanduhr; Rechenzeit je Teil (Summe über Prozesse): %s" % (len(cells), wall, {k: round(v) for k, v in secs.items()}), flush=True)
    with open(os.path.join(out_dir, "sweep_bunching_wallclock.txt"), "w", encoding="utf-8") as fh:
        fh.write("%.0f\n" % wall)
    with open(os.path.join(out_dir, "sweep_bunching_log.txt"), "w", encoding="utf-8") as fh:
        fh.write("Teile %s, %d Prozesse, %d Zellen, Wanduhr %.0f s, Rechenzeit je Teil %s\n" % (",".join(parts), procs, len(cells), wall, {k: round(v) for k, v in secs.items()}))


if __name__ == "__main__":
    a = sys.argv[1:]
    od = OUT_DIR if (not a or a[0] == "-") else a[0]
    npr = a[1] if len(a) > 1 else 4
    sel = a[2] if len(a) > 2 else "alle"
    probe = sel == "probe"
    parts = PARTS if sel in ("alle", "probe") else tuple(x for x in sel.split(",") if x in PARTS)
    main(od, npr, parts, probe)
