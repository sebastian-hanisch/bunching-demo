"""Permalink (Begrenzen), Presets und Zufalls-Seed-Button (Standardmuster aus dem Demo-Portfolio)."""

import random
from dataclasses import dataclass

import streamlit as st

import bun_constants as C


@dataclass(frozen=True)
class SettingSpec:
    url_param: str
    caster: type
    default: object
    lo: float | None = None
    hi: float | None = None
    options: tuple | None = None     # Auswahl-Regler: nur diese Werte sind gültig (die Reihe wurde nur auf diesen Stufen gemessen)


def n_windows(horizon):
    """Zahl der Diagramm-Fenster (je 3 Stunden), die in den Betrachtungszeitraum passen."""
    return int(C.HORIZONS[horizon][0] // (60 * C.WINDOW_HOURS))


SETTING_SPECS = {
    "strategy_select": SettingSpec("strategy", str, C.DEFAULTS["strategy"], options=tuple(C.STRATEGIES)),
    "load_select": SettingSpec("load", float, C.DEFAULTS["load"], options=C.LOAD_CHOICES),
    "noise_select": SettingSpec("noise", str, C.DEFAULTS["noise"], options=tuple(C.NOISE_CHOICES)),
    "buses_select": SettingSpec("buses", int, C.DEFAULTS["buses"], options=C.BUSES_CHOICES),
    "capacity_select": SettingSpec("capacity", str, C.DEFAULTS["capacity"], options=C.CAPACITY_CHOICES),
    "horizon_select": SettingSpec("horizon", str, C.DEFAULTS["horizon"], options=tuple(C.HORIZONS)),
    "window_select": SettingSpec("window", int, C.DEFAULTS["window"], options=tuple(range(max(n_windows(h) for h in C.HORIZONS)))),
    "seed_input": SettingSpec("seed", int, C.DEFAULTS["seed"], 0, C.SEED_MAX),
}
PRESET_KEYS = {spec.url_param: state_key for state_key, spec in SETTING_SPECS.items()}


def allowed_windows(horizon):
    return tuple(range(n_windows(horizon)))


def fix_state():
    """Das Zeitfenster muss in den Betrachtungszeitraum passen (Permalink oder Preset können beides setzen): sonst auf das letzte erlaubte Fenster."""
    horizon = st.session_state.get("horizon_select", SETTING_SPECS["horizon_select"].default)
    ok = allowed_windows(horizon)
    w = st.session_state.get("window_select", SETTING_SPECS["window_select"].default)
    if w not in ok:
        st.session_state["window_select"] = ok[-1]


def init_session_state_defaults():
    for state_key, spec in SETTING_SPECS.items():
        if state_key not in st.session_state:
            st.session_state[state_key] = spec.default


def bounds(state_key):
    spec = SETTING_SPECS[state_key]
    return spec.lo, spec.hi


def clean_value(spec, value):
    """Einen eingelesenen Wert auf den gültigen Bereich bringen: Auswahl-Regler nur auf Stufen (sonst Standard), Zahlen-Regler begrenzt;
    NaN, Infinity und Unlesbares fallen auf den Standard."""
    try:
        value = spec.caster(value)
    except (ValueError, TypeError, OverflowError):
        return spec.default
    if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
        return spec.default
    if spec.options is not None:
        return value if value in spec.options else spec.default
    if spec.lo is not None:
        value = max(spec.lo, value)
    if spec.hi is not None:
        value = min(spec.hi, value)
    return value


def load_permalink_settings():
    """Einmal je Sitzung: Werte aus der Adresszeile übernehmen, auf die gemessenen Stufen und Reglergrenzen begrenzt."""
    if "permalink_loaded" in st.session_state:
        return
    qp = st.query_params
    for state_key, spec in SETTING_SPECS.items():
        if spec.url_param in qp:
            st.session_state[state_key] = clean_value(spec, qp[spec.url_param])
    st.session_state["permalink_loaded"] = True


def sync_query_params(values):
    """`values`: {state_key: aktueller Wert}; die Adresszeile spiegelt die Konfiguration."""
    try:
        for state_key, value in values.items():
            st.query_params[SETTING_SPECS[state_key].url_param] = str(value)
    except Exception:
        pass


def apply_preset(name):
    """Ein Preset setzt JEDEN Regler: was es nicht nennt, bekommt den Standardwert (sonst blieben frühere Änderungen stehen)."""
    for param, state_key in PRESET_KEYS.items():
        st.session_state[state_key] = C.PRESETS[name].get(param, SETTING_SPECS[state_key].default)


def aktives_preset():
    """Name des Presets, dessen Werte GENAU den aktuellen Einstellungen entsprechen, sonst None.

    Zustandslos: verglichen wird jeder Regler aus SETTING_SPECS (ein Preset ohne Eintrag für einen Regler meint dessen Standardwert)
    mit dem Session State. Ein später ergänzter Regler braucht nur seinen Eintrag in SETTING_SPECS (tests/test_layout.py prüft das)."""
    preset_key_of = {state_key: param for param, state_key in PRESET_KEYS.items()}
    for name, preset in C.PRESETS.items():
        if all(
            st.session_state.get(state_key, spec.default) == preset.get(preset_key_of.get(state_key), spec.default)
            for state_key, spec in SETTING_SPECS.items()
        ):
            return name
    return None


def sidebar_presets():
    """Schnellstart oben in der Seitenleiste; das aktive Preset ist hervorgehoben (`type="primary"`)."""
    if not C.PRESETS:
        return
    st.header("🎯 Schnellstart")
    st.caption("Ein Beispielszenario laden:")
    aktiv = aktives_preset()
    for name in C.PRESETS:
        st.button(
            name, width="stretch", on_click=apply_preset, args=(name,), help=C.PRESET_HELP.get(name, ""), key=f"preset_{name}",
            type="primary" if aktiv == name else "secondary",
        )


def randomize_seed():
    st.session_state["seed_input"] = random.randint(0, C.SEED_MAX)
