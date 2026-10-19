"""Preset-Geschichten: Jede stimmt auf dem gezeigten Szenario, und jede Schwelle kippt einzeln an künstlichen Werten (DEMO-PLAYBOOK §12)."""

import pytest

import bun_constants as C
import bun_evaluation as ev
import bun_stories as ST


@pytest.fixture(scope="module")
def analyses():
    return {name: ev.analyse(ST.settings_of(preset)) for name, preset in C.PRESETS.items()}


@pytest.mark.parametrize("name", list(C.PRESETS))
def test_every_preset_story_holds_on_its_scenario(name, analyses):
    assert ST.check(name, analyses[name]), name


def test_every_preset_has_a_criterion_and_a_seed_outside_the_measurement_series():
    assert set(ST.CRITERIA) == set(C.PRESETS)
    assert all(p["seed"] > max(C.SWEEP_SEEDS) for p in C.PRESETS.values())


class _Fake:
    """Analyse mit festen Zahlen je Strategie: Wartezeit, Gesamtreisezeit, Umlaufzeit, CV."""

    def __init__(self, strategy="hw10", verdict="hilft", **stats):
        self.settings = type("S", (), {"strategy": strategy})()
        self.params = type("P", (), {"T0": 60.0})()
        self.verdict = verdict
        base = {"none": dict(wait=16.0, total=50.0, cycle=65.0, cv=1.8), "sched10": dict(wait=4.0, total=37.0, cycle=66.0, cv=0.4), "hw10": dict(wait=4.0, total=39.0, cycle=70.0, cv=0.2)}
        for k, v in stats.items():                      # z. B. none_wait=20.0
            key, metric = k.split("_", 1)
            base[key][metric] = v
        self._stats = base

    def stat(self, key, metric):
        return self._stats[key][metric], 0.0

    def paired_total_difference(self, key, base="none"):
        return self._stats[key]["total"] - self._stats[base]["total"], 0.0


def test_standard_thresholds_are_inclusive():
    assert ST.check_standard(_Fake())
    assert ST.check_standard(_Fake(none_wait=4.0 * ST.STANDARD_RATIO_MIN))
    assert not ST.check_standard(_Fake(none_wait=4.0 * ST.STANDARD_RATIO_MIN - 0.01))
    assert ST.check_standard(_Fake(hw10_cycle=60.0 * ST.STANDARD_CYCLE[0])) and not ST.check_standard(_Fake(hw10_cycle=60.0 * ST.STANDARD_CYCLE[0] - 0.01))
    assert ST.check_standard(_Fake(hw10_cycle=60.0 * ST.STANDARD_CYCLE[1])) and not ST.check_standard(_Fake(hw10_cycle=60.0 * ST.STANDARD_CYCLE[1] + 0.01))
    assert not ST.check_standard(_Fake(verdict="schadet"))


def test_pulse_story():
    assert ST.check_pulk(_Fake("none", "ohne", none_cv=ST.PULSE_CV_MIN)) and not ST.check_pulk(_Fake("none", "ohne", none_cv=ST.PULSE_CV_MIN - 0.01))
    assert not ST.check_pulk(_Fake("hw10", "hilft"))


def test_schedule_story_needs_the_ratio():
    assert ST.check_fahrplan(_Fake(sched10_wait=4.0 * ST.SCHED_RATIO_MIN)) and not ST.check_fahrplan(_Fake(sched10_wait=4.0 * ST.SCHED_RATIO_MIN - 0.01))


def test_collapse_story():
    assert ST.check_zusammenbruch(_Fake(verdict="zusammenbruch", hw10_cycle=60.0 * ST.COLLAPSE_CYCLE_MIN))
    assert not ST.check_zusammenbruch(_Fake(verdict="zusammenbruch", hw10_cycle=60.0 * ST.COLLAPSE_CYCLE_MIN - 0.01))
    assert not ST.check_zusammenbruch(_Fake(verdict="hilft", hw10_cycle=100.0))


def test_harm_stories():
    assert ST.check_zu_viele_busse(_Fake(verdict="schadet", hw10_total=51.0)) and not ST.check_zu_viele_busse(_Fake(verdict="hilft", hw10_total=51.0))
    assert ST.check_volle_busse(_Fake(verdict="schadet", hw10_wait=20.0)) and not ST.check_volle_busse(_Fake(verdict="schadet", hw10_wait=16.0))


def test_headway_story_needs_the_gain():
    assert ST.check_seltene_busse(_Fake(sched10_total=39.0 + ST.HEADWAY_GAIN_MIN + 0.01)) and not ST.check_seltene_busse(_Fake(sched10_total=39.0 + ST.HEADWAY_GAIN_MIN - 0.01))
