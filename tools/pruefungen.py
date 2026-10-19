"""Pflichtprüfungen AP 0 für den Bunching-Kern.

Aufruf:  python -B tools/pruefungen.py rng|orakel|erhaltung|nullspalten|determinismus <zweiter Ordner>|timing|alle
Schreibt pruefungen_<teil>.json in den Rohdatenordner (Umgebungsvariable BUN_RAW_DIR, sonst ../oepnv-planung/messreihe_bunching_ap0).
Zufall nur aus dem Kern (`bun_rng`: SplitMix64 / Stream); der Kern wird nicht verändert, nur importiert.

 rng           Poisson-Sampler (Mittel und Varianz, mu = 0,3 bis 45, 200 000 Ziehungen, |z| <= 3,5), `ln` / `exp_neg` gegen math.log / math.exp (relativ < 1e-14),
               `Stream` gegen `SplitMix64` (Bit-Gleichheit über 100 000 Zahlen), Erlang-Mittel und -Variationskoeffizient
 orakel        Handrechnungen T3 bis T10 der Vorab-Reihe auf dem neuen Kern (konstanter Takt, Gleichgewichtstakt, ein Bus, Wartezeit-Paradox mit endlichem B,
               dichter Konvoi, Strategien ohne Störung, Wachstumsrate gegen `growth_per_hour`), Kapazität (Platzgrenze unendlich gegen riesig, Erhaltung)
 erhaltung     eingestiegen = ausgestiegen + an Bord, Zahl der Busse, Ringfolge, Kachelung, erzeugt = eingestiegen + wartend, Besetzung <= Platzgrenze (120 Seeds je Strategie)
 nullspalten   Sweep-Spalten mit lauter Nullen; Strategievarianten, deren Ergebnis einer anderen bitgleich ist
 determinismus (a) zweimal rechnen, bitgleich; (b) zwei Sweep-Läufe (Rohdatenordner gegen Ordner im Argument) bitgleich
 timing        Rechenzeiten der Live-Pfade
"""
import os

for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import json  # noqa: E402
import math  # noqa: E402
import platform  # noqa: E402
import random  # noqa: E402
import statistics  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
DEMO = os.path.dirname(HERE)
sys.path.insert(0, DEMO)

from bun_rng import SplitMix64, Stream, erlang, exp_neg, ln, poisson  # noqa: E402
from bun_sim import BIN, INF, Params, derived, mean_se, simulate  # noqa: E402
import bun_theory as TH  # noqa: E402

RAW = os.environ.get("BUN_RAW_DIR") or os.path.join(DEMO, "..", "oepnv-planung", "messreihe_bunching_ap0")
OUT = {}


def dump(name, obj):
    fn = os.path.join(RAW, "pruefungen_%s.json" % name)
    with open(fn, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1, default=str)
    print("geschrieben:", fn)


def rec(store, name, ok, **kw):
    store[name] = dict(ok=bool(ok), **kw)
    print(("OK   " if ok else "FAIL "), name, {k: (round(v, 6) if isinstance(v, float) else v) for k, v in kw.items() if not isinstance(v, (list, dict))}, flush=True)


# ------------------------------------------------------------------------------------------------ rng
def part_rng():
    out = {}
    # Poisson-Sampler
    rows, worst_m, worst_v = [], 0.0, 0.0
    for mu in (0.3, 4.0, 19.0, 27.0, 45.0):
        rs = Stream(12345 + int(mu * 10))
        n = 200000
        xs = [poisson(rs, mu) for _ in range(n)]
        mean = sum(xs) / n
        var = sum((x - mean) ** 2 for x in xs) / (n - 1)
        z_m = (mean - mu) / math.sqrt(mu / n)
        z_v = (var - mu) / math.sqrt((2 * mu * mu + mu) / n)
        worst_m, worst_v = max(worst_m, abs(z_m)), max(worst_v, abs(z_v))
        rows.append(dict(mu=mu, mean=mean, var=var, z_mean=z_m, z_var=z_v))
    rec(out, "T1_poisson_momente", worst_m <= 3.5 and worst_v <= 3.5, max_abs_z_mean=worst_m, max_abs_z_var=worst_v, ziehungen=200000, zeilen=rows)
    # ln, exp_neg gegen math
    r = random.Random(20261019)
    xs = [10 ** r.uniform(-300, 300) for _ in range(20000)] + [r.random() for _ in range(100000)] + [1 + 1e-9 * i for i in range(1, 2000)] + [1 - 1e-9 * i for i in range(1, 2000)] \
        + [2.0 ** e for e in range(-1000, 1000, 7)] + [0.5, 0.7071067811865476, 0.7071067811865475, 1.4142135623730951, 3.0, 10.0]
    worst_ln = 0.0
    for x in xs:
        a, b = ln(x), math.log(x)
        if b != 0.0:
            worst_ln = max(worst_ln, abs(a - b) / abs(b))
        else:
            worst_ln = max(worst_ln, abs(a))
    mus = [r.uniform(0, 20) for _ in range(100000)] + [0.0, 1e-12, 0.5, 20.0, 19.999999] + [0.001 * i for i in range(1, 2000)]
    bands = [(0, 2), (2, 5), (5, 10), (10, 15), (15, 20)]
    band_max = {}
    for lo, hi in bands:
        band_max["%d-%d" % (lo, hi)] = max(abs(exp_neg(m) - math.exp(-m)) / math.exp(-m) for m in mus if lo <= m <= hi)
    worst_ex = max(band_max.values())
    mus_big = [20.0 + 0.1 * i for i in range(0, 300)]
    worst_ex_big = max(abs(exp_neg(m) - math.exp(-m)) / math.exp(-m) for m in mus_big)
    rec(out, "T1b_ln_gegen_math", worst_ln < 1e-14, max_rel_ln=worst_ln, bereich_ln="1e-300 bis 1e300 und (0,1)", punkte_ln=len(xs))
    rec(out, "T1b_exp_neg_gegen_math", worst_ex < 1e-14, max_rel_exp_neg=worst_ex, bereich_exp="0 bis 20", max_rel_je_bereich=band_max,
        info_max_rel_exp_neg_20_bis_50=worst_ex_big, punkte_exp=len(mus), bemerkung="Quadrieren der Taylor-Reihe verstärkt den Rundungsfehler mit 2^k; die Plattformstabilität bleibt (nur Grundrechenarten), die Genauigkeit liegt bei mu bis 20 unter 1e-13")
    # Stream gegen SplitMix64
    allok, nums = True, 0
    for seed in (1, 2, 30, 101, 160, 7 + (1 << 40), 30 + (23 << 40), 123456789012345678 % (1 << 64)):
        a, b = SplitMix64(seed), Stream(seed)
        for _ in range(100000 if seed in (1, 7 + (1 << 40)) else 12000):
            if a.uniform() != b.uniform():
                allok = False
                break
            nums += 1
    rec(out, "T1c_stream_gleich_splitmix64", allok, zahlen=nums)
    # Erlang
    rows, ok = [], True
    for k in (1, 2, 3, 6, 25, 100):
        rs = Stream(777 + k)
        n = 200000
        xs = [erlang(rs, k, 2.1) for _ in range(n)]
        mu = sum(xs) / n
        sd = math.sqrt(sum((x - mu) ** 2 for x in xs) / (n - 1))
        z = (mu - 2.1) / (2.1 / math.sqrt(k) / math.sqrt(n))
        cv = sd / mu
        rows.append(dict(k=k, mean=mu, cv=cv, cv_soll=1 / math.sqrt(k), z_mean=z))
        ok &= abs(z) <= 3.5 and abs(cv / (1 / math.sqrt(k)) - 1) < 0.015
    rec(out, "T2_erlang_stoerung", ok, zeilen=rows)
    dump("rng", out)
    return out


# ------------------------------------------------------------------------------------------------ Hilfen
def tile_total(p, res):
    """Summe der Abfahrtsintervalle aller Haltestellen (Kachelzeit) aus der Aufzeichnung: Endstand minus Anfangsstand von last_dep."""
    h0, D0, m = derived(p)
    N, B = p.N, p.B
    pos0 = [0] * B if p.start == "convoy" else [int(round(b * N / B)) % N for b in range(B)]
    init = [-min((pos0[b] - j) % N for b in range(B)) * (m + D0) for j in range(N)]
    last = list(init)
    for (_, j, ta, dep) in res["trace"]:
        if dep > last[j]:
            last[j] = dep
    return sum(last) - sum(init)


def sim(seed, **kw):
    return simulate(Params(**kw), seed)


# ------------------------------------------------------------------------------------------------ orakel
def part_orakel():
    out = {}
    # T3 ohne Störung, ohne Rückkopplung
    for d0 in (0.0, 0.25):
        rs = [sim(sd, d0=d0, s=0.0, erlang_k=0, T_end=240.0, T_warm=60.0, delta=0.0) for sd in range(1, 31)]
        h0 = rs[0]["h0"]
        w, se = mean_se([r["wait"] for r in rs])
        pred = h0 / 2 if d0 == 0 else (h0 - d0) ** 2 / (2 * h0)
        cvmax = max(r["cv"] for r in rs)
        rec(out, "T3_konstanter_abstand_d0=%g" % d0, cvmax < 1e-9 and abs(w - pred) < 3 * se + 1e-9, h0=h0, wait=w, se=se, prognose=pred, cv_max=cvmax)
    # T4 Gleichgewichtstakt mit Rückkopplung (erwartete Fahrgastzahlen)
    for s_ in (0.02, 0.05):
        p = Params(s=s_, erlang_k=0, det=True, T_end=1200.0, T_warm=900.0, delta=0.0)
        h_eq, D_eq, w_pred = TH.equilibrium(p)
        r = simulate(p, 1)
        rec(out, "T4_gleichgewicht_kappa=%.3f" % (s_ * p.lam), abs(r["hbar"] - h_eq) < 1e-9 * h_eq and abs(r["wait"] - w_pred) < 1e-9 and r["cv"] < 1e-6,
            h_eq=h_eq, hbar=r["hbar"], abweichung_rel=abs(r["hbar"] - h_eq) / h_eq, wait=r["wait"], w_pred=w_pred, wait_abweichung=abs(r["wait"] - w_pred), cv=r["cv"],
            bemerkung="cv hat einen Rundungsboden von rund 3e-8 (Varianz als E[H^2] - E[H]^2, Auslöschung), daher Grenze 1e-6")
    # T5 ein Bus, N = 2: geschlossene Lösung
    p = Params(N=2, B=1, T0=10.0, s=0.1, lam=1.0, erlang_k=0, det=True, T_end=720.0, T_warm=60.0, delta=0.0)
    h0, D0, m = derived(p)
    kap = p.s * p.lam
    Tcl = (p.N * m + p.N * p.d0 / (1 + kap)) / (1 - p.N * kap / (1 + kap))
    Dcl = (p.d0 + kap * Tcl) / (1 + kap)
    r = simulate(p, 1)
    gcl = Tcl - Dcl
    rec(out, "T5_ein_bus_geschlossene_loesung", abs(r["cycle"] - Tcl) < 1e-9 * Tcl and abs(r["wait"] - gcl ** 2 / (2 * Tcl)) < 1e-9,
        cycle=r["cycle"], cycle_pred=Tcl, wait=r["wait"], wait_pred=gcl ** 2 / (2 * Tcl))
    # T6 Wartezeit-Paradox bei d0 = s = 0, Erlang k = 1 (exponentiell), endliches B
    p = Params(d0=0.0, s=0.0, erlang_k=1, T_end=300 * 60.0, T_warm=100 * 60.0, delta=0.0)
    rs = [simulate(p, sd) for sd in range(1, 31)]
    diffs = [r["wait"] - r["hbar"] * (1 + r["cv"] ** 2) / 2 for r in rs]
    dm, dse = mean_se(diffs)
    w, wse = mean_se([r["wait"] for r in rs])
    cvs, cvse = mean_se([r["cv"] for r in rs])
    hb, _ = mean_se([r["hbar"] for r in rs])
    B = p.B
    rec(out, "T6_wartezeit_paradox_identitaet", abs(dm) < 3 * dse + 1e-9, diff_mean=dm, diff_se=dse, wait=w, wait_se=wse, cv=cvs, cv_se=cvse, hbar=hb,
        prognose_wait_aus_cv=hb * (1 + cvs ** 2) / 2)
    cv2_pred = TH.independent_bus_cv(B) ** 2
    rec(out, "T6b_unabhaengige_busse_B/(B+1)", abs(w / hb - B / (B + 1)) < 3 * wse / hb + 0.02 and abs(cvs ** 2 - cv2_pred) < 3 * 2 * cvs * cvse + 0.02,
        wait_ueber_h=w / hb, erwartet=B / (B + 1), cv2=cvs ** 2, cv2_erwartet=cv2_pred)
    # T7 dichter Konvoi
    p = Params(start="convoy", erlang_k=0, det=True, s=0.04, lam=0.5, T_end=3600.0, T_warm=1200.0, delta=0.05)
    Tc = TH.convoy_cycle(p)
    r = simulate(p, 1)
    rec(out, "T7_konvoi_umlaufzeit", abs(r["cycle"] - Tc) < 0.01 * Tc, cycle=r["cycle"], prognose=Tc, abweichung_rel=abs(r["cycle"] - Tc) / Tc, sigma=p.sigma)
    # T8 Strategien ohne Störung
    p = Params(s=0.0, erlang_k=0, strat="hw", eta=1.2, c=1, hold_max=10.0, T_end=720.0, T_warm=360.0, delta=0.0)
    r = simulate(p, 1)
    rec(out, "T8a_headway_holding_soll_1.2", abs(r["cycle"] - 1.2 * p.T0) < 0.02 * p.T0, cycle=r["cycle"], prognose=1.2 * p.T0, cv=r["cv"])
    p = Params(s=0.0, erlang_k=0, strat="sched", slack=0.2, c=1, T_end=720.0, T_warm=360.0, delta=0.0)
    r = simulate(p, 1)
    rec(out, "T8b_fahrplan_puffer_0.2", abs(r["cycle"] - 1.2 * p.T0) < 0.02 * p.T0, cycle=r["cycle"], prognose=1.2 * p.T0, cv=r["cv"])
    for eta in (0.9, 1.0):
        p = Params(s=0.0, erlang_k=0, strat="hw", eta=eta, c=1, hold_max=10.0, T_end=720.0, T_warm=360.0, delta=0.0)
        r = simulate(p, 1)
        # η·T0 gilt nur, wenn der Soll-Takt über dem freien Takt liegt; bei η < 1 bleibt der freie Takt (T0)
        soll = max(eta, 1.0) * p.T0
        rec(out, "T8c_headway_eta=%g" % eta, abs(r["cycle"] - soll) < 0.02 * p.T0, cycle=r["cycle"], prognose=soll)
    # T10 Wachstumsrate der Abstandsabweichung (linearisiert, deterministisch, kleiner Anstoß)
    for Bq, s_, tend, kk_ in ((2, 0.04, 12, 0.01), (8, 0.06, 12, 1e-6), (8, 0.10, 8, 1e-6)):
        p = Params(B=Bq, s=s_, erlang_k=0, det=True, kick=kk_, delta=0.0, T_end=tend * 60.0, T_warm=0.0, bins=True)
        N = p.N
        h_eq, D_eq, _ = TH.equilibrium(p)
        r = simulate(p, 1)
        b = r["bins"]
        std = []
        for i in range(len(b["Hn"])):
            if b["Hn"][i]:
                mu = b["H"][i] / b["Hn"][i]
                std.append(math.sqrt(max(b["H2"][i] / b["Hn"][i] - mu * mu, 0.0)))
            else:
                std.append(float("nan"))
        pred = TH.growth_per_hour(p)
        pts = [(BIN / 60.0 * (i + 0.5), math.log(sd)) for i, sd in enumerate(std) if i >= 2 and sd == sd and 1e-8 < sd < 0.03 * h_eq]
        if len(pts) >= 3:
            xs = [x for x, _ in pts]
            ys = [y for _, y in pts]
            mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
            slope = sum((x - mx) * (y - my) for x, y in pts) / sum((x - mx) ** 2 for x in xs)
        else:
            slope = float("nan")
        rec(out, "T10_wachstumsrate_B=%d_kappa=%.3f" % (Bq, p.s * p.lam), abs(slope / pred - 1) <= 0.05, rate_gemessen_je_h=slope, rate_prognose_je_h=pred,
            abweichung_rel=slope / pred - 1, punkte=len(pts))
    # Kapazität: capa = inf gegen riesige Platzgrenze (bitgleich), Erhaltung und Platzgrenze
    worst, same = 0.0, True
    for strat, extra in (("none", {}), ("sched", dict(c=1, slack=0.1)), ("hw", dict(c=1, eta=1.0, hold_max=3.0)), ("hw", dict(c=3, eta=0.9, hold_max=2.0))):
        for sd in range(1, 11):
            a = simulate(Params(strat=strat, T_end=600.0, T_warm=120.0, **extra), sd)
            b_ = simulate(Params(strat=strat, T_end=600.0, T_warm=120.0, capa=10 ** 9, **extra), sd)
            for key in ("wait", "long", "ride", "cv", "cycle", "hold", "bunch", "hbar", "npass", "total"):
                if repr(a[key]) != repr(b_[key]):
                    same = False
                    worst = max(worst, abs(a[key] - b_[key]) / max(1e-9, abs(a[key])))
    rec(out, "T_cap1_gleich_wie_unbegrenzt", same, max_rel_abweichung=worst)
    ok, mx = True, 0
    for capa in (40, 60, 80):
        for sd in range(1, 21):
            r = simulate(Params(T_end=600.0, T_warm=120.0, capa=capa), sd)
            ok &= abs(r["generated"] - r["boarded"] - r["queued"]) < 1e-9 and r["maxload"] <= capa
            mx = max(mx, r["maxload"])
    rec(out, "T_cap2_erhaltung_kapazitaetsgrenze", ok, maxload=mx)
    dump("orakel", out)
    return out


# ------------------------------------------------------------------------------------------------ erhaltung
def part_erhaltung():
    out = {}
    allok = True
    res9 = {}
    cfgs = (("none", {}, INF), ("sched", dict(c=3, slack=0.05), INF), ("hw", dict(eta=0.9, hold_max=2.0, c=1), INF), ("hw+capa60", dict(strat="hw", eta=0.9, hold_max=2.0, c=1), 60),
            ("none+capa40", dict(strat="none"), 40))
    for name, extra, capa in cfgs:
        strat = name.split("+")[0]
        kw = dict(extra)
        kw.setdefault("strat", strat)
        p = Params(T_end=600.0, T_warm=60.0, capa=capa, trace_from=0.0, trace_to=1e9, **kw)
        ok = True
        zs = []
        cnt = dict(boarded_gleich=0, nbus=0, ring=0, kachel=0, erzeugt=0, last=0)
        for sd in range(1, 121):
            r = simulate(p, sd)
            c1 = r["boarded"] == r["alighted"] + r["onboard"]
            c2 = r["nbus"] == p.B
            c3 = bool(r["ring_ok"])
            c4 = abs(r["tile_resid"]) < 1e-6
            c5 = abs(r["generated"] - r["boarded"] - r["queued"]) < 1e-9
            c6 = r["maxload"] <= capa
            cnt["boarded_gleich"] += c1
            cnt["nbus"] += c2
            cnt["ring"] += c3
            cnt["kachel"] += c4
            cnt["erzeugt"] += c5
            cnt["last"] += c6
            ok &= c1 and c2 and c3 and c4 and c5 and c6
            tile = tile_total(p, r)
            zs.append((r["generated"] - p.lam * tile) / math.sqrt(p.lam * tile))
        zm, zse = mean_se(zs)
        zsd = math.sqrt(sum((z - zm) ** 2 for z in zs) / (len(zs) - 1))
        ok &= abs(zm) < 3 * zse and 0.6 < zsd < 1.5
        res9[name] = dict(ok=ok, z_mittel=zm, z_sd=zsd, **cnt)
        allok &= ok
    rec(out, "T9_erhaltung", allok, seeds=120, **res9)
    dump("erhaltung", out)
    return out


# ------------------------------------------------------------------------------------------------ Determinismus
def _same(a, b):
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(_same(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    return repr(a) == repr(b)


def part_determinismus(dir2=None):
    out = {}
    cfgs = [dict(), dict(strat="sched", c=1, slack=0.1), dict(strat="hw", c=1, eta=1.0, hold_max=3.0), dict(strat="hw", capa=60), dict(strat="none", capa=40, T_end=1440.0),
            dict(N=30, B=10, bins=True, trace_from=0.0, trace_to=1e9), dict(erlang_k=25, strat="sched", c=3, slack=0.05), dict(det=True, erlang_k=0, start="convoy")]
    allok, n = True, 0
    for cfg in cfgs:
        for sd in (1, 7, 30, 101):
            a = simulate(Params(**cfg), sd)
            b = simulate(Params(**cfg), sd)
            allok &= _same(a, b)
            n += 1
    rec(out, "determinismus_zweimal_gleicher_lauf", allok, laeufe=n)
    if dir2:
        total, same_n, bad, files = 0, 0, [], []
        for fn in sorted(os.listdir(RAW)):
            if not fn.endswith(".jsonl") or not os.path.exists(os.path.join(dir2, fn)):
                continue
            files.append(fn)
            with open(os.path.join(RAW, fn), encoding="utf-8") as f1, open(os.path.join(dir2, fn), encoding="utf-8") as f2:
                d1 = {json.dumps(json.loads(l)["key"]): json.loads(l) for l in f1}
                d2 = {json.dumps(json.loads(l)["key"]): json.loads(l) for l in f2}
            for k, r2 in d2.items():
                r1 = d1.get(k)
                if r1 is None:
                    bad.append((fn, k, "fehlt in Lauf 1"))
                    continue
                for key in ("m", "traj"):
                    if key in r2:
                        total += 1
                        if r1.get(key) == r2[key]:
                            same_n += 1
                        else:
                            bad.append((fn, k, key))
        rec(out, "determinismus_sweep_lauf2", total > 0 and not bad, dateien=files, bloecke=total, bitgleich=same_n, abweichend=bad[:10])
    dump("determinismus", out)
    return out


# ------------------------------------------------------------------------------------------------ Nullspalten
def part_nullspalten():
    out = {}
    cnt = {}
    for fn in ("x2", "x3", "x4", "x5", "x6", "x7", "x8"):
        with open(os.path.join(RAW, fn + ".jsonl"), encoding="utf-8") as fh:
            for line in fh:
                r = json.loads(line)
                ks = json.dumps(r["key"])
                fam = "none" if '"none"' in ks else ("hw" if '"hw' in ks else ("sched" if '"sched' in ks else "sonst"))
                capfree = r["params"].get("capa", "inf") in ("inf", 10 ** 9)
                for key in ("wait", "bunch", "hold", "long", "fullshare", "ride", "cv", "cycle"):
                    vs = [v for v in r["m"][key] if v is not None]
                    z = bool(vs) and all(v == 0.0 for v in vs)
                    kk = (fn, fam, key, "ohne Platzgrenze" if capfree else "mit Platzgrenze")
                    cnt.setdefault(kk, [0, 0])
                    cnt[kk][0] += z
                    cnt[kk][1] += 1
    rows = [dict(datei=k[0], familie=k[1], kennzahl=k[2], platzgrenze=k[3], nullzellen=v[0], zellen=v[1], ganze_spalte=(v[0] == v[1])) for k, v in sorted(cnt.items()) if v[0]]

    def erklaert(r):
        return ((r["kennzahl"] == "hold" and r["familie"] == "none") or (r["kennzahl"] == "fullshare" and r["platzgrenze"] == "ohne Platzgrenze")
                or (r["kennzahl"] == "bunch" and r["familie"] == "hw"))

    spalten = [r for r in rows if r["ganze_spalte"]]
    unerklaert = [r for r in spalten if not erklaert(r)]
    einzel = [r for r in rows if not r["ganze_spalte"]]
    rec(out, "nullspalten", not unerklaert, ganze_spalten=spalten, unerklaerte_ganze_spalten=unerklaert, einzelne_nullzellen=einzel,
        bemerkung="Nullzellen bei geregeltem Betrieb: Schwelle (gebündelt, Wartezeit > 1,5 h_soll) nie erreicht; Fahrplan-Halt 0 bei Überlast (Busse immer verspätet); Platzgrenze 120 nie voll")
    # Strategievarianten, die einer anderen bitgleich sind (Wartezeit je Seed) und jede Variante gegen "ohne Regelung"
    ident = {}
    for fn, cond_hz in (("x2", ("basis", "schicht")), ("x2", ("basis", "stat"))):
        rows2 = {}
        with open(os.path.join(RAW, fn + ".jsonl"), encoding="utf-8") as fh:
            for line in fh:
                r = json.loads(line)
                if r["key"][0] == cond_hz[0] and r["key"][1] == cond_hz[1]:
                    rows2[json.dumps(r["key"][2])] = r["m"]["wait"]
        none = rows2['"none"']
        gleich_none = [k for k, v in rows2.items() if v == none and k != '"none"']
        byvec = {}
        for k, v in rows2.items():
            byvec.setdefault(json.dumps(v), []).append(k)
        dup = [ks for ks in byvec.values() if len(ks) > 1]
        ident["%s/%s" % cond_hz] = dict(varianten=len(rows2), gleich_ohne_regelung=gleich_none, gleiche_ergebnisse=dup)
    # Gitter: Obergrenze / Parameter, die bitgleich wirken
    grp = {}
    with open(os.path.join(RAW, "x4.jsonl"), encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            k = r["key"]
            if k[0] == "basis" and k[1] == "train":
                grp[json.dumps(k[2:])] = r["m"]["wait"]
    by = {}
    for k, v in grp.items():
        by.setdefault(json.dumps(v), []).append(k)
    dup4 = [ks for ks in by.values() if len(ks) > 1]
    ident["x4/basis/train"] = dict(varianten=len(grp), gruppen_bitgleich=len(dup4), zellen_in_gruppen=sum(len(g) for g in dup4), beispiele=dup4[:8])
    out["varianten"] = ident
    rec(out, "jede_strategievariante_weicht_ab_x2", all(not v["gleich_ohne_regelung"] and not v["gleiche_ergebnisse"] for k, v in ident.items() if k.startswith("basis")),
        details={k: v for k, v in ident.items() if k.startswith("basis")})
    dump("nullspalten", out)
    return out


# ------------------------------------------------------------------------------------------------ Timing
def timeit(fn, n):
    ts = []
    for i in range(n):
        t0 = time.perf_counter()
        fn(i + 1)
        ts.append(time.perf_counter() - t0)
    ts.sort()
    return dict(median=statistics.median(ts), p90=ts[max(0, int(0.9 * len(ts)) - 1)], max=ts[-1], n=n)


def part_timing():
    out = dict(python=platform.python_version(), maschine=platform.processor() or platform.machine(), system=platform.platform())
    S = {"none": dict(strat="none"), "sched": dict(strat="sched", c=1, slack=0.1), "hw": dict(strat="hw", c=1, eta=1.0, hold_max=3.0)}
    rows = []
    for N, B in ((24, 8), (24, 6), (24, 10), (30, 10), (24, 24)):
        for hrs in (10, 40):
            for sn, sd in S.items():
                p = Params(N=N, B=B, T_end=hrs * 60.0, T_warm=hrs * 6.0, **sd)
                rows.append(dict(N=N, B=B, stunden=hrs, strategie=sn, **timeit(lambda s: simulate(p, s), 30 if hrs == 10 else 10)))
    for capa in (30, 60):
        for sn in ("none", "hw"):
            p = Params(T_end=600.0, T_warm=120.0, capa=capa, **S[sn])
            rows.append(dict(N=24, B=8, stunden=10, strategie=sn + "+Platzgrenze %d" % capa, **timeit(lambda s: simulate(p, s), 30)))
    p = Params(T_end=40 * 60.0, T_warm=600.0, capa=30)
    rows.append(dict(N=24, B=8, stunden=40, strategie="none+Platzgrenze 30 (überlastet)", **timeit(lambda s: simulate(p, s), 10)))
    p = Params(s=0.2, T_end=480.0, T_warm=0.0)
    rows.append(dict(N=24, B=8, stunden=8, strategie="none, kappa=0,1 (Zusammenbruch)", **timeit(lambda s: simulate(p, s), 10)))
    out["laeufe"] = rows
    # Live-Ziel: drei Strategien nacheinander, 10 Seeds (Standardfall, 10 h)
    def drei(n, **extra):
        def f(_):
            for sd in S.values():
                for seed in range(1, n + 1):
                    simulate(Params(T_end=600.0, T_warm=120.0, **sd, **extra), seed)
        return f
    t = {}
    for name, extra in (("drei Strategien x 10 Seeds (10 h)", {}), ("drei Strategien x 30 Seeds (10 h)", {}), ("drei Strategien x 10 Seeds (10 h, Platzgrenze 60)", dict(capa=60))):
        n = 30 if "30 Seeds" in name else 10
        t[name] = timeit(drei(n, **extra), 3)
    out["live"] = t
    # Zeit-Weg-Lauf mit trace, alle drei Strategien (ein Seed, 10 h) und mit 40 h Fenster
    def zeitweg(hours):
        def f(_):
            for sd in S.values():
                simulate(Params(T_end=hours * 60.0, T_warm=0.0, trace_from=0.0, trace_to=hours * 60.0, bins=True, **sd), 1)
        return f
    out["zeit_weg"] = {"drei Strategien, 10 h, trace + bins": timeit(zeitweg(10), 20), "drei Strategien, 24 h, trace + bins": timeit(zeitweg(24), 10)}
    out["ueber_1s"] = [r for r in rows if r["median"] > 1.0] + [dict(name=k, **v) for k, v in {**t, **out["zeit_weg"]}.items() if v["median"] > 1.0]
    rec(out, "timing_live_unter_1s", t["drei Strategien x 10 Seeds (10 h)"]["median"] < 1.0, median=t["drei Strategien x 10 Seeds (10 h)"]["median"])
    dump("timing", out)
    return out


PARTS = {"rng": part_rng, "orakel": part_orakel, "erhaltung": part_erhaltung, "nullspalten": part_nullspalten, "timing": part_timing}

if __name__ == "__main__":
    a = sys.argv[1:] or ["alle"]
    if a[0] == "determinismus":
        part_determinismus(a[1] if len(a) > 1 else None)
    elif a[0] == "alle":
        for k in ("rng", "orakel", "erhaltung", "nullspalten", "determinismus", "timing"):
            if k == "determinismus":
                part_determinismus(None)
            else:
                PARTS[k]()
    else:
        PARTS[a[0]]()
