"""Limite de tempo por lance (aprofundamento iterativo), decisão do Lucas em 2026-11-02."""

import time

import pytest

from luna.adapters import new_game
from luna.evolution import TRAINING_SEARCH, EvolutionConfig
from luna.genome import Genome
from luna.player import official_factory
from luna.promotion import PromotionConfig, official_search
from luna.search import MOVE_TIME_LIMIT, SearchConfig, Searcher

MIDDLEGAME = "r1bq1rk1/pp2bppp/2n1pn2/3p4/2PP4/2N1PN2/PP1B1PPP/R2QKB1R w KQ - 0 9"


def test_without_limit_the_iterative_search_picks_the_same_move():
    genome = Genome.reference()
    for depth in (1, 2, 3):
        fixed = Searcher(genome, SearchConfig(depth=depth, quiescence_depth=2))
        timed = Searcher(genome, SearchConfig(depth=depth, quiescence_depth=2, time_limit=600))
        a = fixed.choose_move(new_game("python-chess", MIDDLEGAME))
        b = timed.choose_move(new_game("python-chess", MIDDLEGAME))
        assert a == b and fixed.last_score == timed.last_score


@pytest.mark.parametrize("backend", ["chess_engine", "python-chess"])
def test_time_limit_stops_the_search_and_still_plays(backend):
    state = new_game(backend, MIDDLEGAME)
    fen = state.fen()
    searcher = Searcher(Genome.reference(), SearchConfig(depth=8, time_limit=0.5))
    t = time.monotonic()
    move = searcher.choose_move(state)
    assert time.monotonic() - t < 3  # profundidade 8 levaria minutos
    assert move in state.legal_moves() and searcher.last_score is not None
    assert state.fen() == fen  # a busca interrompida desfez seus lances
    assert searcher._deadline is None


def test_mate_in_one_is_found_with_the_limit():
    state = new_game("python-chess", "6k1/5ppp/8/8/8/8/5PPP/R5K1 w - - 0 1")
    searcher = Searcher(Genome.reference(), SearchConfig(depth=6, time_limit=5))
    assert state.uci(searcher.choose_move(state)) == "a1a8"


def test_fourteen_seconds_everywhere(monkeypatch):
    assert MOVE_TIME_LIMIT == 14.0
    assert TRAINING_SEARCH.time_limit == 14.0
    assert (
        EvolutionConfig.from_dict({"match": {"search": {"depth": 2}}}).match.search.time_limit
        == 14.0
    )
    assert official_search().time_limit == official_search(3).time_limit == 14.0
    assert official_search(time_limit=0).time_limit is None
    assert PromotionConfig().match_config().search.time_limit == 14.0
    monkeypatch.delenv("LUNA_DEPTH", raising=False)
    monkeypatch.delenv("LUNA_TIME_LIMIT", raising=False)
    assert official_factory().searcher.config.time_limit == 14.0
    monkeypatch.setenv("LUNA_TIME_LIMIT", "0")
    assert official_factory().searcher.config.time_limit is None
