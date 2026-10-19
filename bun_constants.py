"""Konstanten: Modellannahmen, Reglerstufen, benannte Haltestrategien, Farben und Presets.

Alle Modellannahmen sind frei gesetzt (kein Messwert): Sie stehen hier an einer Stelle und im README in der Annahmen-Tabelle. Die Regler bieten nur Stufen an,
auf denen die Messreihe gerechnet wurde."""

# --- Linie (Ring) -------------------------------------------------------------------------------------------------------
N_STOPS = 24                 # Haltestellen
LAM = 0.5                    # Fahrgäste je Haltestelle und Minute
T0 = 60.0                    # Soll-Umlaufzeit (min)
D0 = 0.25                    # Grundhalt je Haltestelle (min)
DELTA = 0.05                 # Mindestabstand zweier Busse am Steg (min)

# --- Reglerstufen -----------------------------------------------------------------------------------------------------
LOAD_CHOICES = (0.12, 0.24, 0.48, 0.72, 0.96, 1.2)          # σ = N · s · λ
NOISE_CHOICES = {"schwach": 25, "mittel": 6, "stark": 3}    # Erlang-Form k; Variationskoeffizient 1/√k
NOISE_LABELS = {"schwach": "schwach (cv 0,2)", "mittel": "mittel (cv ≈ 0,41)", "stark": "stark (cv ≈ 0,58)"}
BUSES_CHOICES = (2, 3, 4, 6, 8, 12, 24)
CAPACITY_CHOICES = ("inf", "120", "80", "60", "50")
CAPACITY_LABELS = {"inf": "unbegrenzt", "120": "120 Plätze", "80": "80 Plätze", "60": "60 Plätze", "50": "50 Plätze"}
HORIZONS = {"schicht": (600.0, 120.0), "stationaer": (2400.0, 600.0)}   # (Simulationsende, Einschwingzeit) in Minuten
HORIZON_LABELS = {"schicht": "10-h-Schicht (2 h Einschwingzeit)", "stationaer": "stationär (40 h, 10 h Einschwingzeit)"}
WINDOW_HOURS = 3
SEED_MAX, DEFAULT_SEED = 9999, 503
LIVE_SEEDS = 10              # Live-Mittel über diese Zahl aufeinanderfolgender Zufalls-Seeds
SWEEP_SEEDS = tuple(range(1, 31))   # feste Zufalls-Seeds der Messreihe: nie ein einzelner Seed als Befund

# --- Benannte Haltestrategien (jede einzeln gemessen) ---------------------------------------------------------------------
STRATEGIES = {
    "none": dict(label="keine Regelung", strat="none"),
    "sched5": dict(label="Fahrplan-Holding, Puffer 5 %", strat="sched", c=1, slack=0.05),
    "sched10": dict(label="Fahrplan-Holding, Puffer 10 %", strat="sched", c=1, slack=0.10),
    "sched20": dict(label="Fahrplan-Holding, Puffer 20 %", strat="sched", c=1, slack=0.20),
    "hw09": dict(label="Headway-Holding, η 0,9", strat="hw", c=1, eta=0.9, hold_max=3.0),
    "hw10": dict(label="Headway-Holding, η 1,0", strat="hw", c=1, eta=1.0, hold_max=3.0),
    "field": dict(label="Feldregel (jede 3. Haltestelle, η 0,8, Obergrenze 2 min)", strat="hw", c=3, eta=0.8, hold_max=2.0),
}
DEFAULT_STRATEGY = "hw10"
COMPARE_STRATEGIES = ("none", "sched10", "hw10")      # immer mitgerechnet, damit der Vergleich nicht von der Wahl abhängt

# --- Schwellen der Meldung ------------------------------------------------------------------------------------------------
PULSE_CV = 1.2               # Variationskoeffizient der Abstände, ab dem von einem Pulk gesprochen wird
COLLAPSE_CYCLE = 1.4         # Umlaufzeit mehr als so viel mal Soll-Umlaufzeit: Zusammenbruch
LONG_WAIT = 1.5              # Wartezeit über so viel mal Soll-Takt zählt als „lange gewartet“

COLOR_NONE = "#b04a4a"
COLOR_SCHED = "#4c78a8"
COLOR_HW = "#2F6B65"
COLOR_FIELD = "#c8872b"
COLOR_IDEAL = "#7f7f7f"
STRATEGY_COLOR = {"none": COLOR_NONE, "sched5": COLOR_SCHED, "sched10": COLOR_SCHED, "sched20": COLOR_SCHED, "hw09": COLOR_HW, "hw10": COLOR_HW, "field": COLOR_FIELD}

DEFAULTS = {"strategy": DEFAULT_STRATEGY, "load": 0.48, "noise": "mittel", "buses": 8, "capacity": "inf", "horizon": "schicht", "window": 2, "seed": DEFAULT_SEED}

PRESETS = {
    "Standardfall": {"seed": DEFAULT_SEED},
    "Pulk in wenigen Stunden": {"strategy": "none", "seed": DEFAULT_SEED},
    "Fahrplan-Puffer reicht nicht": {"strategy": "sched10", "load": 0.72, "horizon": "stationaer", "window": 4, "seed": DEFAULT_SEED},
    "Zusammenbruch": {"load": 1.2, "horizon": "stationaer", "window": 4, "seed": DEFAULT_SEED},
    "Zu viele Busse": {"buses": 24, "seed": DEFAULT_SEED},
    "Volle Busse": {"capacity": "50", "seed": DEFAULT_SEED},
    "Seltene Busse": {"buses": 2, "seed": DEFAULT_SEED},
}
PRESET_HELP = {
    "Standardfall": "Ohne Regelung warten die Fahrgäste mehrfach so lange wie beim gleichmäßigen Takt; Headway-Holding hält den Takt, kostet aber Umlaufzeit.",
    "Pulk in wenigen Stunden": "Keine Regelung: Die Abstände streuen, der Variationskoeffizient steigt über 1,2, die Busse laufen als Pulk.",
    "Fahrplan-Puffer reicht nicht": "Bei höherer Last (σ 0,72) bricht der feste Puffer des Fahrplan-Holdings ein; Headway-Holding hält noch.",
    "Zusammenbruch": "Bei σ 1,2 schafft ein einzelner Bus den Einsteige-Aufwand der Linie nicht mehr: Auch die beste Regel scheitert.",
    "Zu viele Busse": "Bei einem Bus je Haltestelle schadet das Halten: Die Wartezeit sinkt, die Fahrzeit im Bus steigt stärker.",
    "Volle Busse": "Bei 50 Plätzen ist die Linie kapazitätsgebunden: Halten kostet Umläufe und verschlechtert die Lage.",
    "Seltene Busse": "Bei nur 2 Bussen (Takt 30 min) reagiert Headway-Holding auf die wirkliche Lücke und schlägt das Fahrplan-Holding.",
}
