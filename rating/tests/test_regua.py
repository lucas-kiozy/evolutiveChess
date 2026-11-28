"""Régua de rating contra a Leela de 4 e 16 nós: estimativa conjunta e pareamento."""

import math

import pytest

from rating.regua import fit, observations, pair_scores


def test_fit_recovers_a_player_against_fixed_opponents():
    # 75% contra um adversário fixo de 2000 equivale a +191 Elo.
    obs = [("x", None, 2000.0, 1.0)] * 300 + [("x", None, 2000.0, 0.0)] * 100
    elo, err = fit(obs)["x"]
    assert elo == pytest.approx(2000 + 400 * math.log10(3), abs=3)
    assert 10 < err < 40


def test_anchor_uncertainty_enters_the_luna_error():
    cal = [("leela:4", None, 2200.0, s) for s in (1.0, 0.0) * 20]
    luna = [("luna", "leela:4", 0.0, s) for s in (1.0, 0.0, 0.5) * 20]
    few = fit(cal + luna)
    many = fit(cal * 10 + luna)
    assert few["luna"][0] == pytest.approx(2200, abs=5)
    assert few["luna"][1] > many["luna"][1]  # calibração maior, erro menor


def test_observations_and_pairs():
    rows = [
        {"a": "leela:16", "b": "sf:2300", "sf_elo": 2300, "score_a": 0.5},
        {"a": "luna", "b": "leela:16", "pair": 0, "score_a": 1.0},
        {"a": "luna", "b": "leela:16", "pair": 0, "score_a": 0.0},
        {"a": "luna", "b": "leela:4", "pair": 0, "score_a": 0.5},
    ]
    assert observations(rows)[0] == ("leela:16", None, 2300.0, 0.5)
    assert observations(rows)[1] == ("luna", "leela:16", 0.0, 1.0)
    assert pair_scores(rows) == {"leela:16": [0.5]}  # o par de 4 nós está incompleto
