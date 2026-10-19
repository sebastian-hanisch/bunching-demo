"""Handrechnungen (Orakel und Anzeige) zur Ringlinie: Gleichgewichtstakt, Wachstumsrate des Bunchings, Konvoi-Umlaufzeit, Wartezeit-Formel.

Symbole: κ = s · λ (zusätzliche Haltezeit je zusätzlicher Wartezeit-Minute an einer Haltestelle), σ = N · κ (Einsteige-Aufwand der ganzen Linie je Minute),
a = κ / (1 + κ), L = N / B (Haltestellen je Bus)."""

import cmath
import math

from bun_sim import Params, derived


def equilibrium(p: Params):
    """Gleichmäßiger Takt mit Rückkopplung (erwartete Fahrgastzahlen, keine Störung): Takt h_eq, Haltezeit D_eq und mittlere Wartezeit (h − D)² / (2h)."""
    h0, D0, m = derived(p)
    kap = p.s * p.lam
    h = (p.N * m / p.B + p.N * p.d0 / (p.B * (1 + kap))) / (1 - p.N * kap / (p.B * (1 + kap)))
    D = (p.d0 + kap * h) / (1 + kap)
    return h, D, (h - D) ** 2 / (2 * h)


def growth_per_stop(a, L, B):
    """Wachstumsrate je Halt der schnellsten Mode aus der linearen Stabilitätsrechnung: ρ = 1 + a (ρ − e^{iθ} ρ^{1−L}), θ = 2π k / B (Newton-Verfahren)."""
    best = 0.0
    for kk in range(1, B):
        th = 2 * math.pi * kk / B
        rho = complex(1 + 2 * a, 0.0)
        for _ in range(200):
            f = rho - 1 - a * (rho - cmath.exp(1j * th) * rho ** (1 - L))
            df = 1 - a * (1 - cmath.exp(1j * th) * (1 - L) * rho ** (-L))
            rho = rho - f / df
        best = max(best, math.log(abs(rho)))
    return best


def growth_per_hour(p: Params):
    """Wachstumsrate der Abstandsabweichung je Stunde (Verzug um L = N / B Halte berücksichtigt)."""
    kap = p.s * p.lam
    a = kap / (1 + kap)
    h_eq, _, _ = equilibrium(p)
    stops_per_h = 60.0 * p.N / (p.B * h_eq)
    return stops_per_h * growth_per_stop(a, p.N // p.B, p.B)


def convoy_cycle(p: Params):
    """Umlaufzeit eines dichten Konvois (alle Busse zusammen, der erste nimmt alle Wartenden mit); Obergrenze für den freien Betrieb.
    Der Nenner wird bei σ = 1 + κ null: Ein einzelner Bus schafft den Einsteige-Aufwand der Linie nicht mehr (Zusammenbruch, Ergebnis unendlich)."""
    h0, D0, m = derived(p)
    kap = p.s * p.lam
    Delta = (p.B - 1) * (p.delta + p.d0 + kap * p.delta)
    num = p.N * m + p.N * (p.d0 - kap * Delta) / (1 + kap)
    den = 1 - p.N * kap / (1 + kap)
    return num / den if den > 0 else float("inf")


def mean_wait_formula(hbar, cv):
    """Wartezeit-Paradox: bei zufällig eintreffenden Fahrgästen und Abstandsmittel h̄ mit Variationskoeffizient CV warten sie im Mittel h̄ (1 + CV²) / 2."""
    return hbar * (1.0 + cv * cv) / 2.0


def independent_bus_cv(B):
    """Variationskoeffizient der Abstände, wenn B Busse unabhängig umlaufen (zufällige Aufstellung auf dem Ring): CV² = (B − 1) / (B + 1)."""
    return math.sqrt((B - 1.0) / (B + 1.0))
