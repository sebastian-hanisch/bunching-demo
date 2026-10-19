"""Zufallsquelle und Mathematik: plattformstabil und gegen unabhängige Referenzen geprüft (DEMO-PLAYBOOK §12)."""

import math
import re
from pathlib import Path

import pytest

import bun_rng as R

ROOT = Path(__file__).resolve().parent.parent


def test_splitmix64_matches_the_published_reference_for_seed_0():
    r = R.SplitMix64(0)
    assert [r.next() for _ in range(3)] == [16294208416658607535, 7960286522194355700, 487617019471545679]


def test_the_block_stream_is_bit_identical_to_the_scalar_generator():
    for seed in (0, 1, 12345, (7 << 40) + 503):
        a, b = R.Stream(seed), R.SplitMix64(seed)
        assert all(a.uniform() == b.uniform() for _ in range(5000))     # über mehr als zwei Blöcke


def test_uniform_stays_strictly_between_zero_and_one():
    r = R.Stream(9)
    xs = [r.uniform() for _ in range(20000)]
    assert 0.0 < min(xs) and max(xs) < 1.0 and abs(sum(xs) / len(xs) - 0.5) < 0.01


@pytest.mark.parametrize("x", [1e-12, 1e-9, 0.01, 0.3, 0.5, 0.7071, 0.9, 1.0, 1.7, 33.3, 1e6])
def test_own_logarithm_matches_the_library(x):
    assert R.ln(x) == pytest.approx(math.log(x), rel=1e-14, abs=1e-15)


@pytest.mark.parametrize("mu", [0.0, 0.01, 0.3, 1.0, 5.0, 20.0])
def test_own_exponential_matches_the_library(mu):
    assert R.exp_neg(mu) == pytest.approx(math.exp(-mu), rel=1e-13)


@pytest.mark.parametrize("mu", [0.3, 3.0, 25.0, 45.0])
def test_poisson_has_mean_and_variance_mu(mu):
    r = R.Stream(100 + int(mu))
    xs = [R.poisson(r, mu) for _ in range(60000)]
    mean = sum(xs) / len(xs)
    var = sum((x - mean) ** 2 for x in xs) / (len(xs) - 1)
    assert abs(mean - mu) < 3.5 * math.sqrt(mu / len(xs))
    assert var == pytest.approx(mu, rel=0.05)


def test_poisson_of_zero_or_negative_mean_is_zero():
    r = R.Stream(1)
    assert R.poisson(r, 0.0) == 0 and R.poisson(r, -1.0) == 0


@pytest.mark.parametrize("k", [3, 6, 25])
def test_erlang_has_the_requested_mean_and_coefficient_of_variation(k):
    r = R.Stream(7 + k)
    xs = [R.erlang(r, k, 2.1) for _ in range(60000)]
    mean = sum(xs) / len(xs)
    sd = math.sqrt(sum((x - mean) ** 2 for x in xs) / (len(xs) - 1))
    assert mean == pytest.approx(2.1, rel=0.01)
    assert sd / mean == pytest.approx(1 / math.sqrt(k), rel=0.02)


def test_the_simulation_does_not_use_library_functions_that_differ_between_platforms():
    """`math.log`, `math.exp`, `random` und `gammavariate` unterscheiden sich in der letzten Stelle; die chaotische Simulation würde je Betriebssystem auseinanderlaufen."""
    for name in ("bun_sim.py", "bun_rng.py"):
        code = re.sub(r'""".*?"""', "", (ROOT / name).read_text(encoding="utf-8"), flags=re.S)
        for forbidden in (r"\bmath\.(log|exp|pow|sin|cos)\b", r"\bimport random\b", r"gammavariate", r"numpy\.random", r"np\.random"):
            assert not re.search(forbidden, code), (name, forbidden)
