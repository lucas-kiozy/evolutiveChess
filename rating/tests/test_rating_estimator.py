import random

import chess
import pytest

from rating.elo import expected_score
from rating.estimator import EstimatorConfig, GameLog, RatingEstimator
from rating.match import play_game
from rating.player import FunctionPlayer, RandomPlayer, load_factory
from rating.stockfish_opponent import TimeControl, find_stockfish


def _fake_runner(true_rating, seed=1):
    rng = random.Random(seed)

    def run(jobs):
        logs = []
        for _factory, elo, luna_white, _cfg in jobs:
            score = 1.0 if rng.random() < expected_score(true_rating, elo) else 0.0
            logs.append(GameLog(elo, "white" if luna_white else "black", score, "", "", 0, 0.0, ""))
        return logs

    return run


def test_adaptive_estimator_converges_and_flags_ready():
    cfg = EstimatorConfig(max_games=400, batch_size=8, stderr_target=25)
    rep = RatingEstimator(lambda: None, cfg, runner=_fake_runner(1800)).run()
    assert abs(rep.estimate.rating - 1800) < 100
    assert rep.ready_for_lichess
    # o adversário foi se aproximando da força real
    assert rep.games[-1].opponent_elo > 1600


def test_weak_player_is_reported_below_floor():
    cfg = EstimatorConfig(max_games=24, batch_size=4)
    rep = RatingEstimator(lambda: None, cfg, runner=_fake_runner(400)).run()
    assert rep.below_anchor_floor
    assert not rep.ready_for_lichess
    assert "abaixo de ~1320" in rep.summary()


def test_play_game_random_vs_random_ends():
    res = play_game(RandomPlayer(1), RandomPlayer(2), max_plies=200)
    assert res.result in {"1-0", "0-1", "1/2-1/2"}
    assert res.plies <= 200
    assert "[Result" in res.pgn


def test_illegal_move_loses():
    bad = FunctionPlayer(lambda fen, legal: "a1a8")
    res = play_game(bad, RandomPlayer(0))
    assert res.result == "0-1" and res.termination == "illegal_move"
    assert res.score_for(chess.WHITE) == 0.0


def test_fools_mate_counts_checks():
    seq = iter(["f2f3", "e7e5", "g2g4", "d8h4"])
    p = FunctionPlayer(lambda fen, legal: next(seq))
    res = play_game(p, p)
    assert res.result == "0-1" and res.termination == "checkmate"
    assert res.checks_by_black == 1 and res.checks_by_white == 0


def test_load_factory():
    f = load_factory("rating.player:random_player_factory")
    assert isinstance(f(), RandomPlayer)
    with pytest.raises(ValueError):
        load_factory("sem_dois_pontos")


def test_time_control_parse():
    assert TimeControl.parse("60+0.6") == TimeControl(60, 0.6)


@pytest.mark.skipif(find_stockfish() is None, reason="Stockfish não instalado")
def test_real_stockfish_beats_random_player():
    cfg = EstimatorConfig(max_games=2, batch_size=2, movetime=0.01, max_plies=300)
    rep = RatingEstimator(load_factory("rating.player:random_player_factory"), cfg).run()
    assert rep.estimate.games == 2
    assert all(g.opponent_elo >= 1320 for g in rep.games)
    assert rep.estimate.score <= 1.0  # aleatório quase nunca pontua
