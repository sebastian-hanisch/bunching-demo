"""Live-Szenario: Einstellungen, Simulation aller Strategien über mehrere Zufalls-Seeds, Kennzahlen, Zeit-Weg-Spur, CV-Verlauf, Theorie und Verdikt in vier Zuständen."""

import math
from dataclasses import dataclass, field

import bun_constants as C
import bun_theory as TH
from bun_sim import BIN, INF, Params, derived, mean_se, simulate

METRICS = ("wait", "ride", "total", "cv", "long", "bunch", "cycle", "hold", "fullshare")


@dataclass(frozen=True)
class Settings:
    strategy: str = C.DEFAULT_STRATEGY
    load: float = 0.48              # σ = N · s · λ
    noise: str = "mittel"           # schwach | mittel | stark
    buses: int = 8
    capacity: str = "inf"           # inf | 120 | 80 | 60 | 50
    horizon: str = "schicht"        # schicht | stationaer
    window: int = 2                 # Zeitfenster des Diagramms (Index, je 3 Stunden)
    seed: int = C.DEFAULT_SEED


def params_of(s: Settings, strategy=None, **extra) -> Params:
    """Simulationsparameter einer Einstellung für die benannte Strategie (Standard: die gewählte)."""
    st = C.STRATEGIES[strategy or s.strategy]
    t_end, t_warm = C.HORIZONS[s.horizon]
    return Params(
        N=C.N_STOPS, B=int(s.buses), T0=C.T0, d0=C.D0, s=s.load / (C.N_STOPS * C.LAM), lam=C.LAM, erlang_k=C.NOISE_CHOICES[s.noise], delta=C.DELTA,
        T_end=t_end, T_warm=t_warm, capa=INF if s.capacity == "inf" else float(s.capacity),
        **{k: v for k, v in st.items() if k != "label"}, **extra)


@dataclass
class Analysis:
    settings: Settings
    params: Params
    runs: dict                         # Strategie -> Liste der Ergebnisse je Zufalls-Seed (mit Bin-Daten)
    trace: dict                        # Strategie -> Ablaufspur im Fenster (Zufalls-Seed = Einstellung)
    window: tuple                      # (von, bis) in Minuten
    time_s: float = 0.0
    extra: dict = field(default_factory=dict)

    @property
    def strategies(self):
        return list(self.runs)

    def stat(self, strategy, metric):
        return mean_se([r[metric] for r in self.runs[strategy]])

    def paired_total_difference(self, strategy, base="none"):
        """Gepaarte Differenz der Gesamtreisezeit (Strategie minus Basis) je Zufalls-Seed: Mittel und Standardfehler."""
        return mean_se([a["total"] - b["total"] for a, b in zip(self.runs[strategy], self.runs[base])])

    @property
    def h0(self):
        return self.params.T0 / self.params.B

    @property
    def verdict(self):
        return verdict_kind(self)


def strategies_for(s: Settings):
    """Immer gerechnet: die Vergleichsstrategien plus die gewählte (in dieser Reihenfolge, ohne Doppelte)."""
    order = list(C.COMPARE_STRATEGIES)
    if s.strategy not in order:
        order.insert(1, s.strategy)
    return order


def window_of(s: Settings):
    t_end, _ = C.HORIZONS[s.horizon]
    n_windows = int(t_end // (60 * C.WINDOW_HOURS))
    w = min(max(int(s.window), 0), n_windows - 1)
    return w * 60.0 * C.WINDOW_HOURS, (w + 1) * 60.0 * C.WINDOW_HOURS


def analyse(s: Settings, n_seeds=C.LIVE_SEEDS) -> Analysis:
    import time

    t0 = time.perf_counter()
    base = params_of(s)
    derived(base)                                      # wirft, wenn die Soll-Umlaufzeit für diese Haltezeiten nicht reicht
    w0, w1 = window_of(s)
    runs, trace = {}, {}
    for key in strategies_for(s):
        p = params_of(s, key, bins=True)
        runs[key] = [simulate(p, s.seed + i) for i in range(n_seeds)]
        trace[key] = simulate(params_of(s, key, trace_from=w0, trace_to=w1), s.seed)["trace"]
    return Analysis(s, base, runs, trace, (w0, w1), time.perf_counter() - t0)


# ------------------------------------------------------------------------------------------------------------------ Verlauf und Theorie
def cv_curve(runs, strategy, bin_min=BIN, rolling=2):
    """Variationskoeffizient der Abfahrtsabstände über die Zeit (gleitend über `rolling` Bins), gepoolt über die Zufalls-Seeds. Liefert (Zeitpunkte in h, CV)."""
    bins = [r["bins"] for r in runs[strategy]]
    nb = len(bins[0]["H"])
    xs, ys = [], []
    for i in range(rolling - 1, nb):
        sl = range(i - rolling + 1, i + 1)
        n = sum(b["Hn"][j] for b in bins for j in sl)
        if not n:
            continue
        mean = sum(b["H"][j] for b in bins for j in sl) / n
        var = sum(b["H2"][j] for b in bins for j in sl) / n - mean * mean
        xs.append((i + 1) * bin_min / 60.0)
        ys.append(math.sqrt(max(var, 0.0)) / mean if mean > 0 else float("nan"))
    return xs, ys


def time_to_pulse(runs, strategy, threshold=C.PULSE_CV, bin_min=BIN, rolling=2):
    """Zeit (h) bis der Variationskoeffizient (gleitend) je Zufalls-Seed erstmals über der Schwelle liegt: Median über die Zufalls-Seeds und Anteil der Zufalls-Seeds,
    die sie erreichen. Median None, wenn weniger als die Hälfte sie erreicht."""
    times = []
    for r in runs[strategy]:
        b = r["bins"]
        hit = None
        for i in range(rolling - 1, len(b["H"])):
            sl = range(i - rolling + 1, i + 1)
            n = sum(b["Hn"][j] for j in sl)
            if not n:
                continue
            mean = sum(b["H"][j] for j in sl) / n
            var = sum(b["H2"][j] for j in sl) / n - mean * mean
            if mean > 0 and math.sqrt(max(var, 0.0)) / mean > threshold:
                hit = (i + 1) * bin_min / 60.0
                break
        times.append(hit)
    reached = sorted(t for t in times if t is not None)
    share = len(reached) / len(times)
    median = reached[len(reached) // 2] if share > 0.5 else None
    return median, share


def theory(a: Analysis):
    """Handrechnungen zum Szenario (ohne Störung gerechnet; die Simulation streut um diese Werte)."""
    p = a.params
    h_eq, d_eq, w_eq = TH.equilibrium(p)
    return dict(h_eq=h_eq, d_eq=d_eq, w_eq=w_eq, growth=TH.growth_per_hour(p) if p.B >= 2 and p.N // p.B >= 1 else float("nan"),
                convoy=TH.convoy_cycle(p), sigma=p.sigma, kappa=p.lam_s, rho=p.sigma / p.B, independent_cv=TH.independent_bus_cv(p.B))


def occupancy(a: Analysis, strategy="none"):
    """Mittlere Besetzung je Bus im Verhältnis zur Platzgrenze (nur bei Platzgrenze): Anteil der Halte, an denen Fahrgäste wegen voller Busse stehen bleiben."""
    return mean_se([r["fullshare"] for r in a.runs[strategy]])


# ------------------------------------------------------------------------------------------------------------------ Verdikt
def verdict_kind(a: Analysis):
    """Vier Zustände: 'ohne' (keine Regelung gewählt), 'zusammenbruch' (gewählte Strategie: Umlaufzeit über COLLAPSE_CYCLE · Soll), 'schadet' (Gesamtreisezeit der gewählten
    Strategie über „ohne Regelung“) und 'hilft'."""
    s = a.settings
    if s.strategy == "none":
        return "ohne"
    if a.stat(s.strategy, "cycle")[0] > C.COLLAPSE_CYCLE * a.params.T0:
        return "zusammenbruch"
    if a.stat(s.strategy, "total")[0] > a.stat("none", "total")[0]:
        return "schadet"
    return "hilft"


def de(x, digits=1):
    """Zahl mit Dezimalkomma; nur die Zahl wird umformatiert, nie ein ganzer Satz (Tausenderpunkt-Falle)."""
    out = f"{x:.{digits}f}"
    if float(out) == 0.0:
        out = out.lstrip("-")
    return out.replace(".", ",")


def verdict(a: Analysis):
    """Meldung (Art, Text); alle Zahlen stammen aus den Läufen des gezeigten Szenarios (Mittel über die Zufalls-Seeds)."""
    s = a.settings
    h0 = a.h0
    w0, w_s = a.stat("none", "wait")[0], a.stat(s.strategy, "wait")[0]
    cyc0, cyc_s = a.stat("none", "cycle")[0], a.stat(s.strategy, "cycle")[0]
    label = C.STRATEGIES[s.strategy]["label"]
    kind = verdict_kind(a)
    if kind == "ohne":
        t, share = time_to_pulse(a.runs, "none")
        when = f"im Median nach {de(t)} h" if t is not None else "in weniger als der Hälfte der Läufe"
        return "warning", (f"**Keine Regelung:** Die Fahrgäste warten im Mittel {de(w0)} min statt {de(h0 / 2)} min beim gleichmäßigen Takt, der Variationskoeffizient der Abstände ist {de(a.stat('none', 'cv')[0], 2)}. "
                           f"Ein Pulk (Variationskoeffizient über {de(C.PULSE_CV)}) entsteht {when} ({de(100 * share, 0)} % der Zufalls-Seeds). Die Umlaufzeit liegt bei {de(cyc0, 0)} min (Soll {de(a.params.T0, 0)}).")
    if kind == "zusammenbruch":
        return "error", (f"**Zusammenbruch:** Auch mit {label} läuft die Umlaufzeit auf {de(cyc_s, 0)} min (Soll {de(a.params.T0, 0)}), die Wartezeit liegt bei {de(w_s)} min. "
                         f"Bei der Last σ = {de(a.params.sigma, 2)} schafft ein einzelner Bus den Einsteige-Aufwand der Linie nicht mehr; ohne Regelung sind es {de(w0)} min.")
    d, se = a.paired_total_difference(s.strategy)
    if kind == "schadet":
        return "warning", (f"**Die Regelung schadet:** Mit {label} sinkt die Wartezeit von {de(w0)} auf {de(w_s)} min, aber die Gesamtreisezeit (Warten plus Fahren) steigt um {de(d)} ± {de(se)} min, "
                           f"weil die Umlaufzeit von {de(cyc0, 0)} auf {de(cyc_s, 0)} min wächst. Das passiert bei sehr vielen Bussen oder voll besetzten Bussen.")
    return "success", (f"**Die Regelung hilft:** Mit {label} sinkt die Wartezeit von {de(w0)} auf {de(w_s)} min (gleichmäßiger Takt: {de(h0 / 2)}), die Gesamtreisezeit um {de(-d)} ± {de(se)} min. "
                       f"Der Preis ist die Umlaufzeit: {de(cyc_s, 0)} statt {de(cyc0, 0)} min ({de(100 * (cyc_s / a.params.T0 - 1), 0)} % über dem Soll).")


def settings_of(values, seed=None):
    """Einstellungen aus einem Preset-Wörterbuch (Schlüssel wie `bun_constants.DEFAULTS`: strategy, load, noise, buses, capacity, horizon, window, seed);
    fehlende Schlüssel bekommen den Standard, `seed` überschreibt den Zufalls-Seed."""
    v = {**C.DEFAULTS, **values}
    return Settings(strategy=v["strategy"], load=float(v["load"]), noise=v["noise"], buses=int(v["buses"]), capacity=v["capacity"], horizon=v["horizon"],
                    window=int(v["window"]), seed=int(v["seed"] if seed is None else seed))
