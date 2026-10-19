"""Live-Auswertung: Parameter aus den Reglern, Fenster, Verläufe, Theorie und Verdikt in vier Zuständen (DEMO-PLAYBOOK §12)."""

import math

import pytest

import bun_constants as C
import bun_evaluation as ev
from bun_sim import INF, Params


@pytest.fixture(scope="module")
def a():
    return ev.analyse(ev.Settings(seed=503))


def test_parameters_from_settings():
    p = ev.params_of(ev.Settings(load=0.72, noise="stark", buses=12, capacity="60", horizon="stationaer"))
    assert p.s == pytest.approx(0.72 / (24 * 0.5)) and p.sigma == pytest.approx(0.72) and p.erlang_k == 3 and p.B == 12 and p.capa == 60.0
    assert (p.T_end, p.T_warm) == (2400.0, 600.0)
    assert ev.params_of(ev.Settings()).capa == INF and ev.params_of(ev.Settings(noise="schwach")).erlang_k == 25


def test_strategy_fields_are_applied():
    p = ev.params_of(ev.Settings(strategy="field"))
    assert (p.strat, p.c, p.eta, p.hold_max) == ("hw", 3, 0.8, 2.0)
    p = ev.params_of(ev.Settings(strategy="sched20"))
    assert (p.strat, p.c, p.slack) == ("sched", 1, 0.2)
    assert ev.params_of(ev.Settings(strategy="hw10"), "none").strat == "none"


def test_compared_strategies_always_include_none_sched10_and_hw10():
    assert ev.strategies_for(ev.Settings()) == ["none", "sched10", "hw10"]
    assert ev.strategies_for(ev.Settings(strategy="field")) == ["none", "field", "sched10", "hw10"]
    assert ev.strategies_for(ev.Settings(strategy="none")) == ["none", "sched10", "hw10"]


def test_window_is_three_hours_and_clamped_to_the_horizon():
    assert ev.window_of(ev.Settings(window=0)) == (0.0, 180.0) and ev.window_of(ev.Settings(window=2)) == (360.0, 540.0)
    assert ev.window_of(ev.Settings(window=9)) == (360.0, 540.0)                    # Schicht: höchstens das dritte Fenster
    assert ev.window_of(ev.Settings(horizon="stationaer", window=4)) == (720.0, 900.0)


def test_analysis_runs_every_strategy_over_the_live_seeds(a):
    assert a.strategies == ["none", "sched10", "hw10"]
    assert all(len(runs) == C.LIVE_SEEDS for runs in a.runs.values())
    assert all(all(w0 <= ta < w1 for _, _, ta, _ in tr) for tr in a.trace.values() for w0, w1 in [a.window])


def test_strategies_reduce_the_wait_and_cost_cycle_time(a):
    assert a.stat("none", "wait")[0] > 2.5 * a.stat("hw10", "wait")[0] and a.stat("none", "wait")[0] > 2.5 * a.stat("sched10", "wait")[0]
    assert a.stat("hw10", "cycle")[0] > a.stat("sched10", "cycle")[0] > a.stat("none", "cycle")[0] - 5.0        # Holding verlängert die Umlaufzeit
    assert a.stat("hw10", "cv")[0] < a.stat("sched10", "cv")[0] < a.stat("none", "cv")[0]


def test_paired_difference_uses_the_same_seeds(a):
    d, se = a.paired_total_difference("hw10")
    direct = sum(h["total"] - n["total"] for h, n in zip(a.runs["hw10"], a.runs["none"])) / C.LIVE_SEEDS
    diffs = [h["total"] - n["total"] for h, n in zip(a.runs["hw10"], a.runs["none"])]
    assert d == pytest.approx(direct) and se == pytest.approx(ev.mean_se(diffs)[1]) and se > 0 and d < 0        # Standardfehler der gepaarten Differenzen


def test_cv_curve_grows_without_control_and_stays_low_with_headway(a):
    xs, none = ev.cv_curve(a.runs, "none")
    _, hw = ev.cv_curve(a.runs, "hw10")
    assert xs[0] == pytest.approx(1.0) and xs[-1] == pytest.approx(10.0)
    assert none[-1] > none[0] and none[-1] > 1.2 and max(hw[1:]) < 0.5


def test_time_to_pulse(a):
    t, share = ev.time_to_pulse(a.runs, "none")
    assert t is not None and 1.0 <= t <= 10.0 and share > 0.5
    assert ev.time_to_pulse(a.runs, "hw10")[0] is None


def test_theory_of_the_standard_case(a):
    th = ev.theory(a)
    assert th["sigma"] == pytest.approx(0.48) and th["kappa"] == pytest.approx(0.02) and th["rho"] == pytest.approx(0.06)
    assert th["convoy"] == pytest.approx(104.438, abs=1e-3) and th["independent_cv"] == pytest.approx(math.sqrt(7 / 9))
    assert 0.8 < th["growth"] < 1.0 and 7.4 < th["h_eq"] < 7.5


def test_an_unreachable_round_trip_is_rejected():
    with pytest.raises(ValueError):
        ev.derived(Params(T0=5.0))


# ------------------------------------------------------------------------------------------------------------------ Verdikt an festen Zahlen
class _Fake:
    """Analyse mit festen Zahlen: Soll-Umlaufzeit 60, Soll-Takt 7,5; je Strategie Wartezeit, Gesamtreisezeit, Umlaufzeit, CV."""

    def __init__(self, strategy="hw10", **stats):
        self.settings = type("S", (), {"strategy": strategy})()
        self.params = type("P", (), {"T0": 60.0, "sigma": 0.48})()
        self.h0 = 7.5
        base = {"none": dict(wait=16.0, total=50.0, cycle=65.0, cv=1.8), "hw10": dict(wait=4.0, total=39.0, cycle=70.0, cv=0.2), "field": dict(wait=9.0, total=40.0, cycle=66.0, cv=0.9)}
        for k, v in stats.items():
            key, metric = k.split("_", 1)
            base[key][metric] = v
        self._stats = base
        self.runs = {"none": [dict(bins=dict(H=[7.5] * 20, H2=[56.25 * 3] * 20, Hn=[1] * 20))]}

    def stat(self, key, metric):
        return self._stats[key][metric], 0.0

    def paired_total_difference(self, key, base="none"):
        return self._stats[key]["total"] - self._stats[base]["total"], 0.25

    verdict = property(ev.verdict_kind)


def test_verdict_states_and_their_boundaries():
    assert _Fake("none").verdict == "ohne"
    assert _Fake(hw10_cycle=60.0 * C.COLLAPSE_CYCLE).verdict == "hilft"                  # genau an der Schwelle noch kein Zusammenbruch
    assert _Fake(hw10_cycle=60.0 * C.COLLAPSE_CYCLE + 0.01).verdict == "zusammenbruch"
    assert _Fake(hw10_total=50.0).verdict == "hilft" and _Fake(hw10_total=50.01).verdict == "schadet"
    assert _Fake(hw10_cycle=100.0, hw10_total=60.0).verdict == "zusammenbruch"          # Zusammenbruch geht vor „schadet“


def test_verdict_text_names_the_numbers():
    kind, text = ev.verdict(_Fake())
    assert kind == "success" and "Die Regelung hilft" in text and "Headway-Holding, η 1,0" in text
    assert "von 16,0 auf 4,0 min" in text and "gleichmäßiger Takt: 3,8" in text and "um 11,0 ± 0,2 min" in text and "70 statt 65 min (17 % über dem Soll)" in text
    kind, text = ev.verdict(_Fake(hw10_total=52.0))
    assert kind == "warning" and "Die Regelung schadet" in text and "um 2,0 ± 0,2 min" in text and "von 65 auf 70 min" in text
    kind, text = ev.verdict(_Fake(hw10_cycle=95.0))
    assert kind == "error" and "Zusammenbruch" in text and "auf 95 min" in text and "σ = 0,48" in text


def test_de_formatting_has_no_negative_zero():
    assert ev.de(-0.04, 1) == "0,0" and ev.de(-1.26, 1) == "-1,3" and ev.de(2.5, 2) == "2,50"
