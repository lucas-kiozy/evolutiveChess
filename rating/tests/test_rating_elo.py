import math
import random

import pytest

from rating.elo import GameResult, estimate_rating, expected_score, games_needed


def test_expected_score_basics():
    assert expected_score(1500, 1500) == pytest.approx(0.5)
    assert expected_score(1900, 1500) == pytest.approx(10 / 11)  # +400 → 10:1
    assert expected_score(1500, 1900) + expected_score(1900, 1500) == pytest.approx(1)


def test_even_score_matches_opponent():
    games = [GameResult(1600, 1.0), GameResult(1600, 0.0)] * 10
    est = estimate_rating(games, prior_sd=10_000)
    assert est.rating == pytest.approx(1600, abs=1)


def test_recovers_true_rating_from_simulation():
    rng = random.Random(7)
    true = 1650
    games = []
    for _ in range(2000):
        opp = rng.choice([1400, 1500, 1600, 1700, 1800, 1900])
        win = rng.random() < expected_score(true, opp)
        games.append(GameResult(opp, 1.0 if win else 0.0))
    est = estimate_rating(games, prior_sd=10_000)
    assert abs(est.rating - true) < 3 * est.stderr
    assert est.stderr < 20


def test_all_wins_stays_finite():
    est = estimate_rating([GameResult(1320, 1.0)] * 10)
    assert math.isfinite(est.rating) and est.rating > 1320


def test_empty_returns_prior():
    est = estimate_rating([])
    assert est.from_prior_only and est.games == 0


def test_invalid_score():
    with pytest.raises(ValueError):
        GameResult(1500, 0.3)


def test_games_needed_is_consistent():
    n = games_needed(55)
    assert 35 <= n <= 45
