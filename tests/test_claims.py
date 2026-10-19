"""Jede Zahl der README (Abschnitte „Warum dieses Problem“ und „Befunde“) ist hier aus data/bun_results.json nachgerechnet (DEMO-PLAYBOOK §4)."""

from pathlib import Path

import bun_results as Rs

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text(encoding="utf-8")
st = Rs.stat_text
ROWS = Rs.strategy_rows("basis/schicht")
N0, S10, H10 = ROWS["none"], ROWS["sched_c1_p10"], ROWS["hw_c1_e1.0_o3"]


def de(x, digits=1):
    out = f"{x:.{digits}f}"
    return out.replace(".", ",")


def has(text):
    assert text in README, text


def test_headline_numbers():
    has(f"im Mittel {st(N0['wait'])} min statt 3,75 min")
    has(f"liegt bei {de(N0['cv']['mean'], 2)}")
    has(f"senkt die Wartezeit auf {st(H10['wait'])} min und kostet {de(100 * (H10['cycle']['mean'] / 60 - 1), 0)} % Umlaufzeit")


def test_what_holding_brings():
    has(f"Wartezeit **{st(N0['wait'])} min** ohne Regelung, **{st(S10['wait'])}** mit Fahrplan-Holding (Puffer 10 %), **{st(H10['wait'])}** mit Headway-Holding (η 1,0)")
    has(f"CV der Abstände {de(N0['cv']['mean'], 2)}, {de(S10['cv']['mean'], 2)} und {de(H10['cv']['mean'], 2)}")
    has(f"{de(S10['cycle']['mean'], 1)} und {de(H10['cycle']['mean'], 1)} min statt 60 min Soll (+{de(100 * (S10['cycle']['mean'] / 60 - 1), 0)} % und +{de(100 * (H10['cycle']['mean'] / 60 - 1), 0)} %)")
    has(f"gepaart um {de(-S10['d_total_gegen_none']['mean'])} ± {de(S10['d_total_gegen_none']['se'])} bzw. {de(-H10['d_total_gegen_none']['mean'])} ± {de(H10['d_total_gegen_none']['se'])} min")


def test_no_sharp_onset():
    rows = {r["sigma"]: r for r in Rs.sigma_table(6)}
    shares = [de(100 * rows[s]["anteil_cv_ueber_1_2_bei_7h"]["p"], 0) for s in (0.06, 0.12, 0.24, 0.36, 0.48)]
    has(" / ".join(shares) + " % bei σ 0,06 / 0,12 / 0,24 / 0,36 / 0,48")
    has(f"wird der CV {de(rows[0.0]['cv_18_24h']['mean'], 2)}")
    has("Mitte der Kurve bei σ ≈ 0,30")
    pts = list(rows.values())
    mid = next(a["sigma"] + (b["sigma"] - a["sigma"]) * (0.5 - a["anteil_cv_ueber_1_2_bei_7h"]["p"]) / (b["anteil_cv_ueber_1_2_bei_7h"]["p"] - a["anteil_cv_ueber_1_2_bei_7h"]["p"])
               for a, b in zip(pts, pts[1:]) if a["anteil_cv_ueber_1_2_bei_7h"]["p"] < 0.5 <= b["anteil_cv_ueber_1_2_bei_7h"]["p"])
    assert de(mid, 2) == "0,30"


def test_collapse():
    c = {r["sigma"]: r for r in Rs.collapse_series()}
    has(f"von {de(c[0.12]['umlaufzeit_ohne']['mean'], 0)} min (σ 0,12) auf {de(c[0.96]['umlaufzeit_ohne']['mean'], 0)} min (σ 0,96)")
    has(f"nur zu {de(100 * c[0.96]['verhaeltnis'], 0)} %")
    has(f"bei {de(c[0.96]['wartezeit']['hw1_10']['mean'])} min bis σ 0,96, bei 1,08 sind es {de(c[1.08]['wartezeit']['hw1_10']['mean'])} min, bei 1,20 schon {de(c[1.2]['wartezeit']['hw1_10']['mean'])} min")
    has(f"({de(c[0.72]['wartezeit']['sched1_10']['mean'])} min bei σ 0,72, {de(c[0.84]['wartezeit']['sched1_10']['mean'])} bei 0,84, {de(c[0.96]['wartezeit']['sched1_10']['mean'])} bei 0,96)")
    base = c[0.12]["wartezeit"]["sched1_20"]["mean"]
    assert c[1.2]["wartezeit"]["sched1_20"]["mean"] < 3 * base < c[1.44]["wartezeit"]["sched1_20"]["mean"]      # 20 % Puffer bricht erst bei σ 1,44
    has("mit 20 % Puffer erst bei σ 1,44")


def test_fleet_and_headway_against_schedule():
    fl = Rs.fleet_equivalent()
    has(f"etwa **{de(fl['basis/sched1_10']['B_eq'])} (Fahrplan) bzw. {de(fl['basis/hw1_10']['B_eq'])} (Headway) statt 8 Busse**")
    hf = Rs.headway_minus_schedule("basis/schicht")
    has("Gesamtreisezeit Headway minus Fahrplan " + f"{de(hf['2']['total'], 2)} min bei 2 Bussen, {de(hf['3']['total'], 2)} bei 3, +{de(hf['4']['total'], 2)} bei 4, +{de(hf['6']['total'], 2)} bei 6, +{de(hf['8']['total'], 2)} bei 8".replace("-", "−"))


def test_harm_cases():
    t = Rs.busse("basis/schicht")
    has(f"ohne Regelung bei {st(t['24/none']['total'])} min, mit Fahrplan-Holding bei {st(t['24/sched1_10']['total'])}, mit Headway-Holding bei {st(t['24/hw1_10']['total'])}")
    cap = Rs.capacity("0.02/schicht")["50"]
    has(f"mittlere Besetzung {de(cap['besetzung_je_kapazitaet'], 2)}) steigt die Wartezeit durch Headway-Holding von {de(cap['none']['wait']['mean'])} auf {de(cap['hw1_10']['wait']['mean'])} min")


def test_rule_against_optimum():
    o = Rs.optimum("basis/total")
    sk = o["optimum"]["sched"]["schluessel"]
    has(f"Kontrollhaltestelle jede {sk[1]}. und {de(100 * sk[2])} % Puffer ({st(o['optimum']['sched']['test'])} min Gesamtreisezeit auf den Test-Seeds, ohne Regelung {st(o['none_test'])})")
    g = o["regeln"]
    has(f"erreicht {de(100 * g['R4 sched c=1 slack=0.10']['gewinnanteil'], 0)} % des möglichen Gewinns, „Fahrplan jede dritte, 10 %“ {de(100 * g['R3 sched c=3 slack=0.10']['gewinnanteil'], 0)} %, Headway (η 1,0) {de(100 * g['R1 hw c=1 eta=1.0 cap=3']['gewinnanteil'], 0)} %, die Feldregel {de(100 * g['R2 hw c=3 eta=0.8 cap=2']['gewinnanteil'], 0)} %")
    has(f"(bei hoher Last und starker Störung {de(100 * Rs.optimum('hart/total')['regeln']['R2 hw c=3 eta=0.8 cap=2']['gewinnanteil'], 0)} %)")
    has(f"{o['breite']['sched_2%']['k']} von {o['breite']['sched_2%']['n']} Gitterzellen liegen innerhalb 2 % des Optimums; in {o['schlechter_als_nichts']['k']} von {o['schlechter_als_nichts']['n']} Zellen")


def test_settling_and_paradox_and_timing():
    s = Rs.settling()["none"]
    has(f"Stunde 1 bei {de(s['wait_h1']['mean'])} min")
    has(f"nach rund {de(s['settle5'], 0)} h")
    has(f"verzerrt die Schicht um {de(100 * s['verzerrung'], 0)} %")
    stat = Rs.strategy_rows("basis/stat")["none"]
    has(f"({st(stat['wait'])} min stationär)")
    has(f"Verhältnis {de(Rs.paradox_rows()[0]['verhaeltnis']['mean'], 2)} ohne Regelung")
    live = Rs.timing()["live"]
    has(f"über 10 Zufalls-Seeds {de(live['drei Strategien x 10 Seeds (10 h)']['median'], 2)} s")
    has(f"über 30 Zufalls-Seeds {de(live['drei Strategien x 30 Seeds (10 h)']['median'], 2)} s")


def test_file_size_and_seeds():
    assert (ROOT / "data" / "bun_results.json").stat().st_size < 250_000
    has("30 Zufalls-Seeds je Zelle")
    assert Rs.SEEDS == 30
