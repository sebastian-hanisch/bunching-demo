"""Zufall und Mathematik für die Simulation, plattformstabil: SplitMix64 (reine Ganzzahl-Arithmetik) und ein eigener Logarithmus und eine eigene
Exponentialfunktion, die nur Grundrechenarten benutzen (IEEE-exakt gerundet).

Warum nicht `math.log` und `math.exp`? Die Simulation ist chaotisch: Ein Unterschied in der letzten Stelle einer Fahrzeit kann nach Stunden die
Reihenfolge zweier Busse umkehren. Die Bibliotheksfunktionen unterscheiden sich zwischen Betriebssystemen in der letzten Stelle, die Grundrechenarten
nicht. So liefert ein Zufalls-Seed auf jeder Plattform dieselbe Simulation.
"""

import math

import numpy as np

_MASK = (1 << 64) - 1
LN2 = 0.6931471805599453
_SQRT_HALF = 0.7071067811865476


class SplitMix64:
    def __init__(self, seed):
        self.state = int(seed) & _MASK

    def next(self):
        self.state = (self.state + 0x9E3779B97F4A7C15) & _MASK
        z = self.state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & _MASK
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & _MASK
        return z ^ (z >> 31)

    def below(self, n):
        """Ganzzahl in 0..n-1 (die Modulo-Verzerrung liegt bei n <= 10^6 unter 1e-13)."""
        return self.next() % n

    def uniform(self):
        """Gleichverteilte Zahl in (0, 1), nie genau 0 oder 1 (53 Bit plus halbe Stufe)."""
        return ((self.next() >> 11) + 0.5) / 9007199254740992.0


class Stream:
    """Dieselbe Zahlenfolge wie `SplitMix64(seed).uniform()`, aber blockweise mit numpy erzeugt: SplitMix64 ist zählerbasiert (Zustand i = seed + i · γ), die i-te Zahl
    hängt also nicht von den vorigen ab. Das macht die Simulation schnell, ohne dass sich ein Bit ändert (Gleichheit mit dem Skalar-Erzeuger: tests/test_rng.py)."""

    BLOCK = 2048

    def __init__(self, seed):
        self.seed = int(seed) & _MASK
        self.index = 0
        self.buf = []
        self.pos = 0

    def _refill(self):
        with np.errstate(over="ignore"):
            idx = np.arange(self.index + 1, self.index + 1 + self.BLOCK, dtype=np.uint64)
            z = np.uint64(self.seed) + np.uint64(0x9E3779B97F4A7C15) * idx
            z = (z ^ (z >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
            z = (z ^ (z >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
            z = z ^ (z >> np.uint64(31))
        self.buf = (((z >> np.uint64(11)).astype(np.float64) + 0.5) / 9007199254740992.0).tolist()
        self.index += self.BLOCK
        self.pos = 0

    def uniform(self):
        try:
            u = self.buf[self.pos]
        except IndexError:
            self._refill()
            u = self.buf[0]
        self.pos += 1
        return u


def ln(x):
    """Natürlicher Logarithmus aus Grundrechenarten: x = m · 2^e (frexp ist exakt), ln m = 2 · artanh((m − 1) / (m + 1)) als Reihe."""
    if not x > 0.0:
        raise ValueError("ln erwartet eine positive Zahl")
    m, e = math.frexp(x)
    if m < _SQRT_HALF:
        m *= 2.0
        e -= 1
    y = (m - 1.0) / (m + 1.0)
    y2 = y * y
    term, total = y, 0.0
    for n in range(1, 28, 2):
        total += term / n
        term *= y2
    return e * LN2 + 2.0 * total


def exp_neg(mu):
    """exp(−mu) für mu >= 0 aus Grundrechenarten: Taylor-Reihe von exp(−mu / 2^k), danach k-mal quadriert."""
    if mu < 0.0:
        raise ValueError("exp_neg erwartet mu >= 0")
    k = 0
    x = mu
    while x > 0.5:
        x *= 0.5
        k += 1
    term, total = 1.0, 1.0
    for n in range(1, 17):
        term *= -x / n
        total += term
    for _ in range(k):
        total *= total
    return total


def poisson(rng, mu):
    """Poisson-Ziehung (Knuth; bei großem mu als Summe unabhängiger Anteile mit höchstens 20)."""
    if mu <= 0.0:
        return 0
    n = 0
    while mu > 20.0:
        n += _knuth(rng, 20.0)
        mu -= 20.0
    return n + _knuth(rng, mu)


def _knuth(rng, mu):
    limit = exp_neg(mu)
    k = 0
    p = rng.uniform()
    while p > limit:
        k += 1
        p *= rng.uniform()
    return k


def erlang(rng, k, mean):
    """Erlang-Ziehung mit Form k und Mittelwert `mean` (Summe von k Exponentialen); Variationskoeffizient 1/√k."""
    p = 1.0
    for _ in range(k):
        p *= rng.uniform()
    return -ln(p) * mean / k
