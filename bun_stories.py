"""Abnahmekriterien der Presets: Jedes Preset erzählt eine Geschichte, und die muss auf dem gezeigten Szenario stimmen.

`check(name, a)` bekommt die Analyse des Presets. Alle Vergleiche stehen innerhalb der Analyse (die Vergleichsstrategien none, sched10 und hw10 werden immer mitgerechnet),
es braucht also keine Referenz-Analyse. Die Schwellen stehen hier einzeln, damit `tests/test_stories.py` jede mit künstlichen Werten an ihrer Grenze prüfen kann."""

import bun_constants as C
import bun_evaluation as ev

# Schwellen
STANDARD_RATIO_MIN = 2.5         # Wartezeit ohne Regelung mindestens so viel mal die mit Regelung
STANDARD_CYCLE = (1.05, 1.25)    # Umlaufzeit mit Regelung im Verhältnis zum Soll
PULSE_CV_MIN = C.PULSE_CV        # ohne Regelung: Variationskoeffizient der Abstände mindestens so hoch
SCHED_RATIO_MIN = 1.5            # Fahrplan-Holding wartet mindestens so viel mal länger als Headway-Holding
COLLAPSE_CYCLE_MIN = C.COLLAPSE_CYCLE
HEADWAY_GAIN_MIN = 0.3           # Gesamtreisezeit: Headway liegt mindestens so viele Minuten unter dem Fahrplan


def _m(a, key, metric):
    return a.stat(key, metric)[0]


def check_standard(a):
    s = a.settings.strategy
    ratio = _m(a, "none", "wait") / _m(a, s, "wait")
    cyc = _m(a, s, "cycle") / a.params.T0
    return a.verdict == "hilft" and ratio >= STANDARD_RATIO_MIN and STANDARD_CYCLE[0] <= cyc <= STANDARD_CYCLE[1]


def check_pulk(a):
    return a.verdict == "ohne" and _m(a, "none", "cv") >= PULSE_CV_MIN


def check_fahrplan(a):
    return _m(a, "sched10", "wait") >= SCHED_RATIO_MIN * _m(a, "hw10", "wait")


def check_zusammenbruch(a):
    return a.verdict == "zusammenbruch" and _m(a, a.settings.strategy, "cycle") >= COLLAPSE_CYCLE_MIN * a.params.T0


def check_zu_viele_busse(a):
    return a.verdict == "schadet" and a.paired_total_difference(a.settings.strategy)[0] > 0


def check_volle_busse(a):
    s = a.settings.strategy
    return a.verdict == "schadet" and _m(a, s, "wait") > _m(a, "none", "wait")


def check_seltene_busse(a):
    return _m(a, "sched10", "total") - _m(a, "hw10", "total") >= HEADWAY_GAIN_MIN


CRITERIA = {
    "Standardfall": check_standard,
    "Pulk in wenigen Stunden": check_pulk,
    "Fahrplan-Puffer reicht nicht": check_fahrplan,
    "Zusammenbruch": check_zusammenbruch,
    "Zu viele Busse": check_zu_viele_busse,
    "Volle Busse": check_volle_busse,
    "Seltene Busse": check_seltene_busse,
}


def settings_of(preset, seed=None):
    """Einstellungen eines Presets (Schlüssel wie in bun_constants.PRESETS); `seed` überschreibt den Zufalls-Seed des Presets."""
    return ev.settings_of(preset, seed=seed)


def check(name, a):
    return bool(CRITERIA[name](a))
