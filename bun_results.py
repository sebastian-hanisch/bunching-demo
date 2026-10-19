"""Vorgerechnete Messreihe (data/bun_results.json, erzeugt von tools/sweep_bunching.py, tools/analyse.py, tools/dump_results.py): Laden und Abfragen.

Nichts hier rechnet im Browser; alle Zahlen stammen aus 30 Zufalls-Seeds je Zelle (siehe `meta`). Statistikfelder haben die Form {n, mean, se, med, p10, p90},
Anteile die Form {k, n, p}."""
import json
import os
import pathlib
from functools import lru_cache

PATH = pathlib.Path(os.environ.get("BUN_RESULTS_PATH") or pathlib.Path(__file__).parent / "data" / "bun_results.json")
INF = float("inf")
SEEDS = 30


def _decode(o):
    """±Unendlich steht in der Datei als "inf" / "-inf" (JSON kennt kein Infinity); hier wieder als Zahl."""
    if isinstance(o, dict):
        return {k: _decode(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_decode(v) for v in o]
    if o == "inf":
        return INF
    if o == "-inf":
        return -INF
    return o


@lru_cache(maxsize=1)
def load():
    with open(PATH, encoding="utf-8") as fh:
        return _decode(json.load(fh))


def meta():
    return load()["meta"]


def model():
    return load()["modell"]


def sigma_table(k=6):
    """Entstehung des Pulks ohne Regelung je Last σ (Erlang-Form k = 6 oder 25): Zeilen mit CV und Wartezeit in drei Phasen, Anteil der Zufalls-Seeds mit CV > 1,2 nach 7 h."""
    return load()["entstehung"][f"sigma_tabelle_k{k}"]["zeilen"]


def time_to_pulse_rows():
    return load()["entstehung"]["zeit_bis_pulk"]


def collapse_series():
    """Zusammenbruch (B = 8): je σ Umlaufzeit ohne Regelung, Konvoi-Formel, Wartezeit je Strategie."""
    return load()["zusammenbruch"]["reihe_B8"]


def collapse_labels():
    return load()["zusammenbruch"]["strategien"]


def strategy_rows(condition="basis/schicht"):
    """Zeilen der Strategietabelle (Standardfall, 10-h-Schicht oder stationär) mit wait, ride, total, cv, long, bunch, cycle, hold, d_total_gegen_none."""
    return {r["id"]: r for r in load()["strategien"][condition]}


def paradox_rows():
    return load()["strategien"]["paradox"]


def busse(condition="basis/schicht"):
    """Wartezeit und Gesamtreisezeit je Zahl der Busse und Strategie: {"B/strategie": {"wait": stat, "total": stat}}."""
    return load()["busse"]["tabellen"][condition]


def busse_labels():
    return load()["busse"]["strategien"]


def bus_counts():
    return load()["busse"]["B"]


def fleet_equivalent():
    return load()["busse"]["fleet_aequivalent"]


def headway_minus_schedule(condition="basis/schicht"):
    return load()["busse"]["headway_minus_fahrplan"][condition]


def optimum(combo="basis/total"):
    """Gitter Regel gegen Optimum: none_test, Optimum, Regeln R1 bis R4 mit Lücke und Gewinnanteil, Breite des Optimums, Fläche Fahrplan (c × Puffer)."""
    return load()["gitter"]["kombinationen"][combo]


def rule_labels():
    return load()["gitter"]["regeln_text"]


def capacity(key="0.02/schicht"):
    """Platzgrenze → Strategie → Kennzahlen (wait, cv, cycle, total, voll_anteil) und Besetzung je Platzgrenze."""
    return load()["kapazitaet"][key]


def sensitivity():
    return load()["sensitivitaet"]


def settling():
    return load()["einschwing"]


def timing():
    return load()["rechenzeit"]


def checks():
    return load()["pruefungen"]


def stat_text(s, digits=1):
    """„Mittel ± Standardfehler“ mit Dezimalkomma; „–“, wenn die Zelle keinen Wert hat (null in der Datei: z. B. kein Umlauf zustande gekommen)."""
    if s is None or s.get("mean") is None:
        return "–"
    if s.get("se") is None:
        return f"{s['mean']:.{digits}f}".replace(".", ",")
    return f"{s['mean']:.{digits}f} ± {s['se']:.{digits}f}".replace(".", ",")


def share_text(p):
    return f"{p['k']} von {p['n']}"
