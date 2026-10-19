"""Orakel-Tests (ORACLE-PLAYBOOK §2): unabhängige Referenzen für die Simulation aus der Theorie der Ringlinie.

1. Gleichgewichtstakt mit Rückkopplung (erwartete Fahrgastzahlen) auf 1e-9.
2. Wartezeit-Paradox: bei d0 = s = 0 ist die Wartezeit h̄ (1 + CV²) / 2; bei B unabhängigen Bussen gilt CV² = (B − 1) / (B + 1) und Wartezeit / h = B / (B + 1).
3. Wachstumsrate einer kleinen Abweichung der Abstände gegen die lineare Stabilitätsrechnung (nur Rückkopplung, keine Störung).
4. Dichter Konvoi gegen die geschlossene Formel; Zusammenbruch bei σ = 1 + κ."""

import math
from dataclasses import replace

import pytest

import bun_theory as TH
from bun_sim import Params, simulate

DET = Params(erlang_k=0, det=True, T_end=1200.0, T_warm=300.0)


def test_equilibrium_headway_and_wait_without_noise():
    h_eq, _d, w_eq = TH.equilibrium(DET)
    r = simulate(replace(DET, T_end=6000.0, T_warm=3000.0), 1)
    assert r["hbar"] == pytest.approx(h_eq, rel=1e-9) and r["wait"] == pytest.approx(w_eq, rel=1e-9)
    assert 7.4 < h_eq < 7.5                             # die Haltezeit hängt an den Wartenden und ist etwas kürzer als beim Soll angesetzt: der Takt weicht leicht vom Soll ab


@pytest.mark.parametrize("B", [4, 8])
def test_waiting_time_paradox_with_independent_buses(B):
    """d0 = s = 0, exponentialverteilte Fahrzeit (Erlang mit Form 1, CV 1): Die Busse laufen unabhängig um, die Abstände werden zufällig."""
    p = Params(B=B, d0=0.0, s=0.0, erlang_k=1, T_end=9000.0, T_warm=600.0)
    runs = [simulate(p, seed) for seed in range(1, 31)]
    hbar = sum(r["hbar"] for r in runs) / len(runs)
    cv = sum(r["cv"] for r in runs) / len(runs)
    wait = sum(r["wait"] for r in runs) / len(runs)
    assert wait == pytest.approx(TH.mean_wait_formula(hbar, cv), rel=0.02)           # Wartezeit-Paradox mit den gemessenen h̄ und CV
    assert cv == pytest.approx(TH.independent_bus_cv(B), rel=0.04)                   # CV² = (B − 1) / (B + 1)
    assert wait / (p.T0 / B) == pytest.approx(B / (B + 1.0), rel=0.04)               # Wartezeit / h = B / (B + 1)


def _sd_by_bin(r):
    b = r["bins"]
    out = []
    for i in range(len(b["H"])):
        n = b["Hn"][i]
        mean = b["H"][i] / n
        out.append(math.sqrt(max(b["H2"][i] / n - mean * mean, 1e-30)))
    return out


@pytest.mark.parametrize("B,s,tol", [(2, 0.04, 0.03), (8, 0.06, 0.06)])
def test_growth_rate_of_a_small_headway_deviation(B, s, tol):
    """Ohne Störung wächst eine kleine Anfangsabweichung (kick) exponentiell; die Rate je Stunde stimmt mit der linearen Stabilitätsrechnung überein
    (Verzug um N / B Halte berücksichtigt; ohne den Verzug wäre sie bis 15 % zu hoch)."""
    p = replace(DET, B=B, s=s, kick=1e-3, T_end=720.0, T_warm=0.0, bins=True)
    sd = _sd_by_bin(simulate(p, 1))
    rate = math.log(sd[10] / sd[6]) / (4 * 0.5)                                       # Bins zu 30 Minuten: Stunden 3 bis 5
    assert rate == pytest.approx(TH.growth_per_hour(p), rel=tol)
    assert rate > 0


def test_growth_rate_rises_with_the_feedback():
    rates = [TH.growth_per_hour(replace(DET, s=s)) for s in (0.01, 0.02, 0.04, 0.08)]
    assert all(b > a for a, b in zip(rates, rates[1:])) and rates[0] > 0


def test_no_feedback_no_growth():
    assert TH.growth_per_hour(replace(DET, s=0.0)) == pytest.approx(0.0, abs=1e-9)


def test_dense_convoy_has_a_pole_at_sigma_equal_one_plus_kappa():
    """Unter σ = 1 + κ ist die Konvoi-Umlaufzeit endlich und wächst mit σ; darüber unendlich."""
    cycles = [TH.convoy_cycle(replace(DET, s=sig / (24 * 0.5))) for sig in (0.12, 0.48, 0.96)]
    assert all(math.isfinite(c) for c in cycles) and cycles[0] < cycles[1] < cycles[2]
    assert TH.convoy_cycle(replace(DET, s=1.2 / (24 * 0.5), T0=90.0)) == math.inf


def test_theory_helpers_for_independent_buses():
    assert TH.independent_bus_cv(8) == pytest.approx(math.sqrt(7 / 9)) and TH.independent_bus_cv(1) == 0.0
    assert TH.mean_wait_formula(7.5, 0.0) == 3.75 and TH.mean_wait_formula(7.5, 1.0) == 7.5
