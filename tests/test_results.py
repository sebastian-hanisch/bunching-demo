"""Vorgerechnete Messreihe (data/bun_results.json): Aufbau, innere Konsistenz und Bitgleichheit der Live-Rechnung gegen die Sweeps."""

import math
from dataclasses import replace

import pytest

import bun_results as Rs
from bun_sim import Params, mean_se, simulate


def test_structure():
    d = Rs.load()
    assert set(d) >= {"meta", "modell", "entstehung", "zusammenbruch", "strategien", "busse", "gitter", "kapazitaet", "sensitivitaet", "einschwing", "rechenzeit", "pruefungen"}
    assert Rs.model()["N"] == 24 and Rs.model()["B"] == 8 and Rs.model()["sigma"] == pytest.approx(0.48) and Rs.model()["h0"] == 7.5
    assert Rs.bus_counts() == [2, 3, 4, 6, 8, 12, 24]
    assert all(r["wait"]["n"] == Rs.SEEDS for r in Rs.strategy_rows().values())


STRATEGIES = {"none": {}, "sched_c1_p10": dict(strat="sched", c=1, slack=0.10), "hw_c1_e1.0_o3": dict(strat="hw", c=1, eta=1.0, hold_max=3.0)}


@pytest.mark.parametrize("key", list(STRATEGIES))
def test_live_computation_is_bit_identical_to_the_series(key):
    """Dieselben 30 Zufalls-Seeds und dieselben Parameter ergeben dieselben Mittel wie die Messreihe (auf die 6 gültigen Stellen der Datei)."""
    row = Rs.strategy_rows("basis/schicht")[key]
    runs = [simulate(replace(Params(), **STRATEGIES[key]), seed) for seed in range(1, 31)]
    for metric in ("wait", "ride", "total", "cv", "cycle", "hold"):
        assert mean_se([r[metric] for r in runs])[0] == pytest.approx(row[metric]["mean"], rel=6e-6, abs=1e-9), metric


def test_sigma_curve_is_continuous_and_monotone():
    rows = Rs.sigma_table(6)
    share = [r["anteil_cv_ueber_1_2_bei_7h"]["p"] for r in rows]
    assert all(b >= a - 0.1 for a, b in zip(share, share[1:])) and share[0] < 0.2 and share[-1] == pytest.approx(1.0, abs=0.05)
    steps = [b - a for a, b in zip(share[:6], share[1:6])]
    assert max(steps) < 0.4                                       # kein Sprung: kein scharfer Kipppunkt
    assert [r["sigma"] for r in rows][:3] == [0.0, 0.06, 0.12]


def test_theory_columns_are_consistent_with_the_model():
    from bun_theory import growth_per_hour

    row = next(r for r in Rs.sigma_table(6) if r["sigma"] == 0.48)
    assert row["wachstum_je_h"] == pytest.approx(growth_per_hour(Params()), rel=1e-3) and Rs.model()["growth_per_hour"] == pytest.approx(row["wachstum_je_h"], rel=1e-3)
    assert Rs.model()["convoy_cycle"] == pytest.approx(104.438, abs=1e-3)


def test_collapse_ordering():
    series = Rs.collapse_series()
    none = [r["wartezeit"]["none"]["mean"] for r in series]
    assert all(b > a for a, b in zip(none, none[1:]))
    low = series[0]["wartezeit"]
    assert max(low["hw1_10"]["mean"], low["sched1_10"]["mean"], low["sched1_20"]["mean"]) < 0.6 * low["none"]["mean"]
    last = [r for r in series if r["umlaufzeit_ohne"]["mean"] is not None and r["konvoi_formel"] != math.inf]
    assert all(r["umlaufzeit_ohne"]["mean"] <= r["konvoi_formel"] + 1e-6 for r in last)      # der dichte Konvoi ist die Obergrenze
    assert all(r["konvoi_formel"] == math.inf for r in series if r["sigma"] >= 1.08)         # Pol bei σ = 1 + κ


def test_holding_costs_cycle_time_and_saves_waiting():
    rows = Rs.strategy_rows("basis/schicht")
    assert rows["hw_c1_e1.0_o3"]["wait"]["mean"] < 0.3 * rows["none"]["wait"]["mean"] and rows["sched_c1_p10"]["wait"]["mean"] < 0.3 * rows["none"]["wait"]["mean"]
    assert rows["hw_c1_e1.0_o3"]["cycle"]["mean"] > rows["sched_c1_p10"]["cycle"]["mean"] > 60.0
    assert rows["hw_c1_e1.0_o3"]["cv"]["mean"] < rows["sched_c1_p10"]["cv"]["mean"] < rows["none"]["cv"]["mean"]


def test_many_buses_make_holding_harmful_and_few_buses_make_it_pay():
    t = Rs.busse("basis/schicht")
    assert t["24/none"]["total"]["mean"] < t["24/sched1_10"]["total"]["mean"] < t["24/hw1_10"]["total"]["mean"]
    assert t["2/hw1_10"]["total"]["mean"] < t["2/none"]["total"]["mean"] - 10.0
    hf = Rs.headway_minus_schedule("basis/schicht")
    assert hf["2"]["total"] < 0 < hf["6"]["total"] and hf["8"]["total"] < hf["24"]["total"]       # Vorzeichenwechsel zwischen wenigen und vielen Bussen


def test_fleet_equivalent_is_above_the_actual_fleet():
    assert all(v["B_eq"] > 8 for k, v in Rs.fleet_equivalent().items() if k.startswith("basis"))


def test_capacity_binds_near_a_load_of_one():
    cap = Rs.capacity("0.02/schicht")
    assert cap["50"]["besetzung_je_kapazitaet"] == pytest.approx(1.04, abs=0.01) and cap["50"]["hw1_10"]["wait"]["mean"] > cap["50"]["none"]["wait"]["mean"]
    assert cap["120"]["hw1_10"]["wait"]["mean"] < 0.5 * cap["120"]["none"]["wait"]["mean"]


def test_the_rule_is_close_to_the_optimum_and_the_field_rule_is_not():
    for combo in ("basis/total", "basis/w2", "basis/wait"):
        g = Rs.optimum(combo)["regeln"]
        assert g["R4 sched c=1 slack=0.10"]["gewinnanteil"] > 0.9 and g["R2 hw c=3 eta=0.8 cap=2"]["gewinnanteil"] < 0.8
    assert Rs.optimum("basis/total")["schlechter_als_nichts"]["k"] > 0


def test_no_stationary_state_without_control():
    s = Rs.settling()
    assert s["none"]["settle5"] > 10 and s["hw1_10"]["settle5"] <= 2 and s["sched1_10"]["settle5"] <= 2


def test_stat_text_handles_null_cells_and_decimal_comma():
    assert Rs.stat_text({"mean": 14.6484, "se": 1.01285}) == "14,6 ± 1,0"
    assert Rs.stat_text({"mean": None, "se": None}) == "–" and Rs.stat_text(None) == "–" and Rs.stat_text({"mean": 2.0, "se": None}) == "2,0"
    assert Rs.share_text({"k": 7, "n": 30}) == "7 von 30"


def test_inf_strings_are_decoded():
    assert Rs._decode({"a": ["inf", "-inf", 1.0]}) == {"a": [math.inf, -math.inf, 1.0]}


def test_every_model_check_passed_except_the_documented_accuracy_of_the_own_exponential():
    failed = [k for k, v in Rs.checks().items() if v.get("ok") is False]
    assert failed == ["T1b_exp_neg_gegen_math"]
    assert Rs.checks()["T1b_exp_neg_gegen_math"]["max_rel_exp_neg"] < 1e-13
