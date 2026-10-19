"""Schreibt aus auswertung.json (tools/analyse.py) die kompakte Ergebnisdatei data/bun_results.json für die App.

Aufruf:  python -B tools/dump_results.py [Pfad zu auswertung.json] [Ausgabedatei]
Standard: BUN_RAW_DIR/auswertung.json (sonst ../oepnv-planung/messreihe_bunching_ap0) -> data/bun_results.json

Regeln: UTF-8, +inf als String "inf", -inf als "-inf", NaN als null. Alle Gleitkommazahlen auf 6 gültige Stellen gerundet, keine Rohdaten, kompakte
Trennzeichen. Statistiken sind {n, mean, se, med, p10, p90}, Anteile {k, n, p}. Oberste Ebene:
  meta, modell, entstehung, zusammenbruch, strategien, busse, gitter, kapazitaet, sensitivitaet, einschwing, rechenzeit, pruefungen
Bedingungen (Störung/Last) heißen wie in der Vorab-Reihe: basis, cv0.2 (Erlang k = 25), cv0.6 (k = 3), kap0.01, kap0.03, hart (k = 3, kappa 0,03).
"""
import json
import math
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
DEMO = os.path.dirname(HERE)
RAW = os.environ.get("BUN_RAW_DIR") or os.path.join(DEMO, "..", "oepnv-planung", "messreihe_bunching_ap0")
SRC = os.path.join(RAW, "auswertung.json")
DST = os.path.join(DEMO, "data", "bun_results.json")
MAX_BYTES = 250 * 1024

STRAT_ID = {
    "keine Regelung": "none",
    "Fahrplan c=1, Puffer 0 %": "sched_c1_p0", "Fahrplan c=1, Puffer 5 %": "sched_c1_p5", "Fahrplan c=1, Puffer 10 %": "sched_c1_p10", "Fahrplan c=1, Puffer 15 %": "sched_c1_p15",
    "Fahrplan c=3, Puffer 10 %": "sched_c3_p10",
    "Headway c=1, η=0.8, Obergrenze 3": "hw_c1_e0.8_o3", "Headway c=1, η=0.9, Obergrenze 3": "hw_c1_e0.9_o3", "Headway c=1, η=1.0, Obergrenze 3": "hw_c1_e1.0_o3",
    "Headway c=1, η=1.1, Obergrenze 3": "hw_c1_e1.1_o3", "Headway c=3, η=0.9, Obergrenze 3": "hw_c3_e0.9_o3", "Headway c=3, η=0.8, Obergrenze 1": "hw_c3_e0.8_o1",
}
STRAT3_LABEL = {"none": "keine Regelung", "sched1_10": "Fahrplan c=1, Puffer 10 %", "sched3_10": "Fahrplan c=3, Puffer 10 %", "sched3_05": "Fahrplan c=3, Puffer 5 %",
                "hw1_09": "Headway c=1, η=0.9", "hw1_10": "Headway c=1, η=1.0", "hw3_09": "Headway c=3, η=0.9", "hw3_10": "Headway c=3, η=1.0"}


def rnd(o):
    if isinstance(o, dict):
        return {str(k): rnd(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [rnd(v) for v in o]
    if isinstance(o, bool):
        return o
    if isinstance(o, float):
        if math.isnan(o):
            return None
        if math.isinf(o):
            return "inf" if o > 0 else "-inf"
        return float("%.6g" % o)
    return o


def pick(d, keys):
    return {k: d[k] for k in keys if k in d}


def entstehung(A):
    out = {}
    for lab, cv in (("k6", "0.4"), ("k25", "0.2")):
        rows = []
        for kap, e in A["x1"]["kcv"][cv].items():
            rows.append(dict(kappa=e["kappa"], sigma=e["sigma"], rho=e["rho"], wachstum_je_h=e["rate"], cv_0_4h=e["cv04"], cv_6_5_7_5h=e["cv7"], cv_18_24h=e["cv18"],
                             wait_0_4h=e["w04"], wait_6_5_7_5h=e["w7"], wait_18_24h=e["w18"], anteil_cv_ueber_1_2_bei_7h=e["share7"], zeit_bis_cv_1_2_median_h=e["t_med"],
                             erreicht_in_24h=e["reach"]))
        out["sigma_tabelle_" + lab] = dict(erlang_k=int(lab[1:]), cv_erlang=1 / math.sqrt(int(lab[1:])), zeilen=rows)
    out["zeit_bis_pulk"] = [dict(variante=("B variiert" if e["variante"] == "B" else "N und B variiert"), B=e["B"], N=e["N"], sigma=e["sigma"], median_h=e["med"],
                                 erreicht_in_24h=e["reach"], cv_18_24h=e["cv18"]) for e in A["x1"]["BN"]]
    v = A["verlauf"]
    out["verlauf_sigma_0_48"] = {sn: dict(stunde=v[sn]["stunde"], cv=v[sn]["cv"], wartezeit=v[sn]["wait"]) for sn in ("none", "hw1_10", "sched1_10") if sn in v}
    return out


def zusammenbruch(A):
    rows = []
    for e in A["x5"]:
        rows.append(dict(sigma=e["sigma"], kappa=e["kappa"], umlaufzeit_ohne=pick(e["cycle"], ("n", "mean", "se", "med", "p10", "p90")), konvoi_formel=e["convoy"], verhaeltnis=e["ratio"],
                         wartezeit={k: v for k, v in e["wait"].items()}))
    bt = [dict(sigma=e["sigma"], kappa=e["kappa"], wartezeit=e["wait"]) for e in A["x5_B"]]
    return dict(strategien=dict(none="ohne Regelung", hw1_10="Headway c=1 η=1,0", sched1_10="Fahrplan c=1 Puffer 10 %", sched1_20="Fahrplan c=1 Puffer 20 %"), reihe_B8=rows, tabelle_B4_8_12=bt)


def strategien(A):
    out = {}
    for cz, blk in A["x2"].items():
        rows = []
        for lab, e in blk.items():
            rows.append(dict(id=STRAT_ID.get(lab, lab), label=lab, wait=e["wait"], ride=e["ride"], total=e["total"], cv=e["cv"], long=e["long"], bunch=e["bunch"], cycle=e["cycle"],
                             hold=e["hold"], d_total_gegen_none=e["d_total"]))
        out[cz] = rows
    out["paradox"] = [dict(label=p["label"], wait=p["wait"], vorhersage=p["pred"], verhaeltnis=p["ratio"]) for p in A["paradox"]]
    return out


def busse(A):
    out = {"strategien": STRAT3_LABEL, "B": [2, 3, 4, 6, 8, 12, 24], "tabellen": {}}
    for cz, blk in A["x3"].items():
        out["tabellen"][cz] = {k: dict(wait=v["wait"], total=v["total"]) for k, v in blk.items()}
    out["fleet_aequivalent"] = A["b_eq"]
    out["headway_minus_fahrplan"] = {}
    for cz in ("basis/schicht", "basis/stat"):
        blk = A["x3"][cz]
        out["headway_minus_fahrplan"][cz] = {str(B): dict(wait=blk["%d/hw1_10" % B]["wait"]["mean"] - blk["%d/sched1_10" % B]["wait"]["mean"],
                                                         total=blk["%d/hw1_10" % B]["total"]["mean"] - blk["%d/sched1_10" % B]["total"]["mean"]) for B in (2, 3, 4, 6, 8, 12, 24)}
    return out


def gitter(A):
    out = {"kombinationen": {}}
    for cz, e in A["x4"].items():
        rec = dict(none_test=e["none_test"], optimum={f: dict(schluessel=v["key"], train=v["train"], test=v["test"]) for f, v in e["opt"].items()},
                   optimum_testseeds=e["opt_testseeds"], regeln={k: dict(test=v["test"], luecke=v["luecke"], gewinnanteil=v["gewinnanteil"]) for k, v in e["regeln"].items()},
                   breite=e["breite"], schlechter_als_nichts=e["schlechter_als_nichts"])
        if "flaeche_sched_test" in e:
            fl = e["flaeche_sched_test"]
            cs = list(fl)
            ps = list(fl[cs[0]])
            rec["flaeche_sched_test"] = dict(c=[int(c) for c in cs], puffer=[float(p) for p in ps], gesamtreisezeit_mittel=[[fl[c][p]["mean"] for p in ps] for c in cs],
                                             gesamtreisezeit_se=[[fl[c][p]["se"] for p in ps] for c in cs])
            rec["obergrenze_wirkung"] = dict(obergrenzen=[0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 100.0], kurven={k: [dict(mean=s["mean"], se=s["se"]) for s in v] for k, v in e["cap_wirkung"].items()})
            rec["c_wirkung"] = {k: v["total"] for k, v in e["c_wirkung"].items()}
        out["kombinationen"][cz] = rec
    out["regeln_text"] = {"R1": "Headway c=1 η=1,0 Obergrenze 3 min", "R2": "Headway c=3 η=0,8 Obergrenze 2 min", "R3": "Fahrplan c=3 Puffer 10 %", "R4": "Fahrplan c=1 Puffer 10 %"}
    out["pro_B"] = {k: dict(none=v["none"], headway=v["hw"], headway_schluessel=v["hw_key"], fahrplan=v["sched"], fahrplan_schluessel=v["sched_key"], differenz_headway_minus_fahrplan=v["diff"],
                            regel_headway=v["R1"], regel_fahrplan=v["R4"]) for k, v in A["x7"].items()}
    return out


def kapazitaet(A):
    out = {}
    for cz, blk in A["x6"].items():
        out[cz] = {("unbegrenzt" if int(c) >= 10 ** 8 else c): {sn: dict(wait=e[sn]["wait"], cv=e[sn]["cv"], cycle=e[sn]["cycle"], total=e[sn]["total"], voll_anteil=e[sn]["fullshare"]["mean"])
                                                               for sn in ("none", "sched1_10", "hw1_10")} | dict(besetzung_je_kapazitaet=e["occ"]) for c, e in blk.items()}
    return out


def sensitivitaet(A):
    return {k: dict(wait=v["wait"], cv=v["cv"], cycle=v["cycle"], total=v["total"]) for k, v in A["x8"].items()}


def einschwing(A):
    return A["warm"]


def pruefungen(A):
    out = {}
    for nm in ("rng", "orakel", "erhaltung", "determinismus", "nullspalten"):
        d = A.get("pr_" + nm)
        if not d:
            continue
        for k, v in d.items():
            if isinstance(v, dict) and "ok" in v:
                out[k] = {kk: vv for kk, vv in v.items() if not isinstance(vv, (list, dict))}
    return out


def build(A):
    return dict(
        meta=dict(stand="2026-10-19", seeds=A["meta"]["seeds"], fenster=A["meta"]["fenster"], ersatz_gamma_durch_erlang=A["meta"]["ersatz"],
                  kern="bun_sim.py (SplitMix64, Erlang-Störung, Warteschlangen-Buchhaltung); Zeit in Minuten, Kennzahlen je Fahrgast",
                  bedingungen=dict(basis="N=24, B=8, T0=60, Erlang k=6, kappa=0,02", **{"cv0.2": "Erlang k=25", "cv0.6": "Erlang k=3", "kap0.01": "s=0,02", "kap0.03": "s=0,06",
                                                                                         "hart": "Erlang k=3 und s=0,06"})),
        modell=pick(A["modell"], ("N", "B", "T0", "d0", "s", "lam", "delta", "erlang_k", "cv_erlang", "h0", "m", "D0", "kappa", "sigma", "rho", "h_eq", "D_eq", "wait_eq", "growth_per_hour", "convoy_cycle")),
        entstehung=entstehung(A), zusammenbruch=zusammenbruch(A), strategien=strategien(A), busse=busse(A), gitter=gitter(A), kapazitaet=kapazitaet(A),
        sensitivitaet=sensitivitaet(A), einschwing=einschwing(A), rechenzeit=A.get("rechenzeit", {}), pruefungen=pruefungen(A))


def main(src=SRC, dst=DST):
    with open(src, encoding="utf-8") as fh:
        A = json.load(fh)
    out = rnd(build(A))
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, separators=(",", ":"))
    size = os.path.getsize(dst)
    print("geschrieben:", dst, "%.0f kB" % (size / 1024.0), "Schlüssel:", list(out))
    if size >= MAX_BYTES:
        print("WARNUNG: Datei größer als 250 kB")
        sys.exit(1)


if __name__ == "__main__":
    main(*(sys.argv[1:3]))
