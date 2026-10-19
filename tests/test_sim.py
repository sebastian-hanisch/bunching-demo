"""Simulation gegen Handrechnung, Erhaltungssätze und eingefrorene Läufe (DEMO-PLAYBOOK §1b)."""

import math
from dataclasses import replace

import pytest

from bun_sim import INF, Params, derived, mean_se, simulate

DET = Params(erlang_k=0, det=True, T_end=1200.0, T_warm=300.0)


def test_derived_values_of_the_standard_case():
    h0, D0, m = derived(Params())
    assert h0 == 7.5 and D0 == pytest.approx(0.25 + 0.04 * 0.5 * 7.5) and m == pytest.approx(60 / 24 - D0)
    assert Params().sigma == pytest.approx(0.48) and Params().lam_s == pytest.approx(0.02)


def test_derived_rejects_a_line_whose_stops_take_longer_than_the_round_trip():
    with pytest.raises(ValueError):
        derived(Params(T0=5.0))


def test_without_noise_and_feedback_the_headway_stays_constant_and_the_wait_is_half_of_it():
    """d0 = s = 0, keine Störung: Abstand 7,5 min für immer, Wartezeit = Abstand / 2 = 3,75 min."""
    r = simulate(replace(DET, d0=0.0, s=0.0), 1)
    assert r["cv"] == pytest.approx(0.0, abs=1e-9) and r["wait"] == pytest.approx(3.75, abs=1e-9) and r["hbar"] == pytest.approx(7.5)


def test_a_fixed_stop_time_shortens_the_waiting_window():
    """Mit Grundhalt 0,25 min steigen die in dieser Zeit eintreffenden Fahrgäste ohne Wartezeit zu: Wartezeit = (h − d0)² / (2h)."""
    r = simulate(replace(DET, s=0.0), 1)
    assert r["wait"] == pytest.approx((7.5 - 0.25) ** 2 / (2 * 7.5), rel=1e-12)


def test_one_bus_against_the_closed_form():
    """Ein Bus: g = N m + (N − 1) D und D = d0 + κ g ergeben D = (d0 + κ N m) / (1 − κ (N − 1)) und die Umlaufzeit N (m + D)."""
    p = replace(DET, B=1, T_end=6000.0, T_warm=600.0)
    m = derived(p)[2]
    kap = p.s * p.lam
    D = (p.d0 + kap * p.N * m) / (1 - kap * (p.N - 1))
    assert simulate(p, 1)["cycle"] == pytest.approx(p.N * (m + D), rel=1e-6)


def test_dense_convoy_against_the_formula():
    from bun_theory import convoy_cycle

    p = replace(DET, start="convoy", T_end=6000.0, T_warm=1000.0)
    assert simulate(p, 1)["cycle"] == pytest.approx(convoy_cycle(p), rel=1e-6)
    assert convoy_cycle(p) == pytest.approx(104.438, abs=1e-3)


@pytest.mark.parametrize("kw,factor", [(dict(strat="sched", slack=0.2), 1.2), (dict(strat="hw", eta=1.2, hold_max=100.0), 1.2), (dict(strat="sched", slack=0.1), 1.1)])
def test_holding_without_noise_gives_the_cycle_time_of_the_rule(kw, factor):
    """Ohne Störung bestimmt die Regel die Umlaufzeit: (1 + Puffer) · T0 bzw. η · T0."""
    assert simulate(replace(DET, **kw), 1)["cycle"] == pytest.approx(factor * 60.0, rel=1e-9)


@pytest.mark.parametrize("strat", ["none", "sched", "hw"])
@pytest.mark.parametrize("capa", [INF, 60])
def test_conservation_laws(strat, capa):
    for seed in range(1, 13):
        r = simulate(replace(Params(), strat=strat, capa=capa, B=6), seed)
        assert r["generated"] - r["boarded"] - r["queued"] == 0                   # erzeugt = eingestiegen + wartend
        assert r["boarded"] - r["alighted"] - r["onboard"] == 0                   # eingestiegen = ausgestiegen + an Bord
        assert r["nbus"] == 6 and r["ring_ok"]                                    # Zahl der Busse, lückenlose Haltestellenfolge
        assert abs(r["tile_resid"]) < 1e-6                                        # Kachelung der Abfahrtsintervalle
        assert r["maxload"] <= capa


def test_generated_passengers_match_the_rate_times_the_run_time_on_average():
    """Die Abfahrtsintervalle aller Haltestellen zerlegen die Laufzeit bis zur letzten Abfahrt: erzeugte Fahrgäste liegen knapp unter λ · N · Laufzeit (die Busse sind am Ende
    noch unterwegs; Mittel über 40 Zufalls-Seeds zwischen 93 und 100 %)."""
    for strat in ("none", "hw"):
        p = replace(Params(), strat=strat)
        ratios = [simulate(p, seed)["generated"] / (p.lam * p.N * p.T_end) for seed in range(1, 41)]
        assert 0.93 < sum(ratios) / len(ratios) < 1.0


def test_noise_free_runs_do_not_depend_on_the_seed():
    a, b = simulate(replace(DET, strat="hw"), 1), simulate(replace(DET, strat="hw"), 99)
    assert a["wait"] == b["wait"] and a["cycle"] == b["cycle"]


def test_the_same_seed_gives_the_same_run_and_other_seeds_differ():
    p = replace(Params(), strat="sched")
    a, b, c = simulate(p, 5), simulate(p, 5), simulate(p, 6)
    assert a["wait"] == b["wait"] and a["cv"] == b["cv"] and a["wait"] != c["wait"]


def test_strategies_share_the_random_numbers_for_paired_comparisons():
    """Die ersten Fahrzeiten sind in allen Strategien gleich (gleicher Strom je Bus); erst die Rückkopplung trennt die Läufe."""
    short = dict(T_end=20.0, T_warm=0.0, trace_from=0.0, trace_to=20.0)
    a, b = simulate(replace(Params(), **short), 4), simulate(replace(Params(), strat="hw", **short), 4)
    assert a["trace"][0][:2] == b["trace"][0][:2]


FROZEN = [  # (Abweichung von Params(), Zufalls-Seed) -> (Wartezeit, Fahrzeit, CV, Umlaufzeit, eingestiegen, Besuche)
    (dict(), 3, (22.18625899348961, 35.6390345321954, 2.1662636114994243, 67.78496446435322, 6701.0, 1344.0)),
    (dict(strat="hw"), 3, (3.8287374059023653, 34.45541088305412, 0.2111470787870572, 70.47540811764847, 7053.0, 1323.0)),
    (dict(strat="sched", capa=60, B=6, erlang_k=3), 3, (29.819951886496213, 33.20960124059813, 0.2952287391752442, 66.4372097319192, 6442.0, 1051.0)),
]


@pytest.mark.parametrize("kw,seed,expected", FROZEN)
def test_frozen_runs(kw, seed, expected):
    """Plattformstabil: Dieselben Ganzzahl- und Grundrechenarten ergeben auf jedem Betriebssystem dieselbe Simulation (auf 1e-9 relativ)."""
    r = simulate(replace(Params(), **kw), seed)
    got = (r["wait"], r["ride"], r["cv"], r["cycle"], r["boarded"], r["visits"])
    assert got == pytest.approx(expected, rel=1e-9)


def test_trace_records_the_stops_of_the_window():
    r = simulate(replace(Params(), trace_from=300.0, trace_to=360.0), 2)
    assert r["trace"] and all(300.0 <= ta < 360.0 and dep >= ta and 0 <= j < 24 and 0 <= b < 8 for b, j, ta, dep in r["trace"])


def test_mean_se():
    mu, se = mean_se([1.0, 2.0, 3.0, float("nan")])
    assert mu == 2.0 and se == pytest.approx(1 / math.sqrt(3))


def test_headway_holding_leaves_no_bunched_departures_and_no_control_leaves_many():
    """Anteil der Abfahrten mit Abstand unter h0 / 2: bei Headway-Holding mit η ≥ 0,5 per Konstruktion null, ohne Regelung groß."""
    hw = [simulate(replace(Params(), strat="hw"), s)["bunch"] for s in range(1, 6)]
    none = [simulate(Params(), s)["bunch"] for s in range(1, 6)]
    assert max(hw) == 0.0 and min(none) > 0.2
