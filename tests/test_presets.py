"""Presets: Vollständigkeit, gültige Werte, Standard-Preset = Standardeinstellungen, Permalink-Bereinigung, Fenster zum Zeitraum."""

import pytest

import bun_constants as C
import bun_evaluation as ev
import bun_presets as P


def test_every_preset_has_help():
    assert set(C.PRESETS) == set(C.PRESET_HELP)
    assert all(C.PRESET_HELP.values())


def test_preset_values_are_valid_steps():
    for name, preset in C.PRESETS.items():
        for param, value in preset.items():
            spec = P.SETTING_SPECS[P.PRESET_KEYS[param]]
            assert P.clean_value(spec, value) == value, (name, param)


def test_preset_windows_fit_into_the_horizon():
    for name, preset in C.PRESETS.items():
        s = ev.settings_of(preset)
        assert s.window in P.allowed_windows(s.horizon), name


def test_default_preset_equals_the_default_settings():
    first = next(iter(C.PRESETS))
    assert ev.settings_of(C.PRESETS[first]) == ev.Settings()


def test_setting_specs_cover_every_url_parameter():
    assert set(P.PRESET_KEYS.values()) == set(P.SETTING_SPECS) and set(C.DEFAULTS) == set(P.PRESET_KEYS)


def test_presets_differ_from_each_other_in_at_least_one_setting():
    settings = [ev.settings_of(p) for p in C.PRESETS.values()]
    assert len(set(settings)) == len(settings)


def test_windows_per_horizon():
    assert P.allowed_windows("schicht") == (0, 1, 2) and len(P.allowed_windows("stationaer")) == 13


@pytest.mark.parametrize("state_key,bad,expected", [
    ("strategy_select", "x", "hw10"), ("load_select", "nan", 0.48), ("load_select", "0.5", 0.48), ("buses_select", "5", 8), ("buses_select", "abc", 8),
    ("window_select", "99", 2), ("seed_input", "-5", 0), ("seed_input", "99999999", C.SEED_MAX), ("capacity_select", "70", "inf"), ("noise_select", "x", "mittel"),
])
def test_clean_value_falls_back_or_clamps(state_key, bad, expected):
    assert P.clean_value(P.SETTING_SPECS[state_key], bad) == expected


def test_settings_of_maps_every_key():
    s = ev.settings_of({"strategy": "sched5", "load": 0.96, "noise": "stark", "buses": 12, "capacity": "60", "horizon": "stationaer", "window": 4, "seed": 7})
    assert s == ev.Settings(strategy="sched5", load=0.96, noise="stark", buses=12, capacity="60", horizon="stationaer", window=4, seed=7)
    assert ev.settings_of({"seed": 1}, seed=9).seed == 9


def test_every_strategy_is_known_and_has_a_label():
    for key, st in C.STRATEGIES.items():
        assert st["label"] and st["strat"] in ("none", "sched", "hw") and key in C.STRATEGY_COLOR
    assert set(C.COMPARE_STRATEGIES) <= set(C.STRATEGIES)
