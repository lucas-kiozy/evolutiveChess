"""Limite de tempo por lance (aprofundamento iterativo), decisão do Lucas em 2026-11-02."""

import time

import pytest

from luna.adapters import new_game
from luna.evolution import TRAINING_SEARCH, EvolutionConfig
from luna.genome import Genome
from luna.player import official_factory
from luna.promotion import OFFICIAL_MOVE_TIME, PromotionConfig, official_search
from luna.search import MOVE_TIME_LIMIT, SearchConfig, Searcher, TimeBudget

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


def test_training_keeps_fourteen_seconds_and_official_games_use_the_budget(monkeypatch):
    assert MOVE_TIME_LIMIT == 14.0
    assert TRAINING_SEARCH.time_limit == 14.0 and TRAINING_SEARCH.budget is None
    assert (
        EvolutionConfig.from_dict({"match": {"search": {"depth": 2}}}).match.search.time_limit
        == 14.0
    )
    assert OFFICIAL_MOVE_TIME == 20.0
    for config in (official_search(), official_search(3), PromotionConfig().match_config().search):
        assert config.time_limit == 20.0
        assert config.budget == TimeBudget(move_time=20.0, extended_time=40.0, max_extensions=5)
    assert official_search(time_limit=0).time_limit is None
    assert official_search(time_limit=0).budget is None
    for var in ("LUNA_DEPTH", "LUNA_TIME_LIMIT", "LUNA_EXTENDED_TIME", "LUNA_EXTENSIONS"):
        monkeypatch.delenv(var, raising=False)
    assert official_factory().searcher.config.budget.move_time == 20.0
    monkeypatch.setenv("LUNA_TIME_LIMIT", "15")
    monkeypatch.setenv("LUNA_EXTENDED_TIME", "30")
    monkeypatch.setenv("LUNA_EXTENSIONS", "3")
    budget = official_factory().searcher.config.budget
    assert (budget.move_time, budget.extended_time, budget.max_extensions) == (15, 30, 3)
    monkeypatch.setenv("LUNA_TIME_LIMIT", "0")
    assert official_factory().searcher.config.time_limit is None
    assert official_factory().searcher.config.budget is None


def test_budget_round_trips_through_dict():
    from dataclasses import asdict

    config = official_search()
    assert SearchConfig.from_dict(asdict(config)) == config


# ---------------------------------------------------------------- orçamento de tempo
# Pedido do Lucas em 2026-11-27: teto normal por lance, parada antecipada com lance
# estável e no máximo ``max_extensions`` lances por partida acima do teto.

OPEN_POSITIONS = [
    MIDDLEGAME,
    "r2q1rk1/ppp2ppp/2np1n2/2b1p1B1/2B1P1b1/2NP1N2/PPP2PPP/R2Q1RK1 w - - 0 8",
    "2r2rk1/pp1bqppp/2nbpn2/3p4/3P4/2PBPN2/PPQN1PPP/R4RK1 w - - 0 12",
    "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
    "r3k2r/ppp2ppp/2n1bn2/2bqp3/8/2NP1NP1/PPP1PPBP/R1BQ1RK1 w kq - 0 9",
]


def _budgeted(depth=12, **budget) -> Searcher:
    config = SearchConfig(depth=depth, budget=TimeBudget(**budget), time_limit=budget["move_time"])
    return Searcher(Genome.reference(), config)


def test_with_plenty_of_time_the_budget_plays_the_fixed_depth_move():
    genome = Genome.reference()
    for depth in (1, 2, 3):
        fixed = Searcher(genome, SearchConfig(depth=depth, quiescence_depth=2))
        budget = TimeBudget(move_time=600, extended_time=600)
        timed = Searcher(genome, SearchConfig(depth=depth, quiescence_depth=2, budget=budget))
        a = fixed.choose_move(new_game("python-chess", MIDDLEGAME))
        b = timed.choose_move(new_game("python-chess", MIDDLEGAME))
        assert a == b and fixed.last_score == timed.last_score
        assert timed.last_info["depth"] == depth and not timed.last_info["extended"]


def test_without_credits_no_move_goes_past_the_cap():
    searcher = _budgeted(move_time=0.6, extended_time=5.0, max_extensions=0, safety=0.1)
    for fen in OPEN_POSITIONS:
        state = new_game("chess_engine", fen)
        t = time.monotonic()
        move = searcher.choose_move(state)
        assert time.monotonic() - t < 0.6 + 0.15
        assert move in state.legal_moves() and state.fen() == fen
        assert not searcher.last_info["extended"]
    assert searcher.extensions_used == 0


def test_extensions_are_limited_per_game_and_reset_on_new_game():
    # drop_cp muito negativo: toda camada conta como "instável", então todo lance quer
    # estender. Só os 2 primeiros podem; depois, o teto volta a ser fixo.
    searcher = _budgeted(
        move_time=0.4,
        extended_time=0.8,
        max_extensions=2,
        drop_cp=-1e9,
        unstable_from_depth=1,
        safety=0.05,
    )
    infos = []
    for fen in OPEN_POSITIONS:
        searcher.choose_move(new_game("chess_engine", fen))
        infos.append(dict(searcher.last_info))
    assert [i["extended"] for i in infos] == [True, True, False, False, False]
    assert searcher.extensions_used == 2
    assert all(i["seconds"] < 0.8 + 0.15 for i in infos)
    assert all(i["seconds"] < 0.4 + 0.1 for i in infos[2:])
    searcher.new_game()
    searcher.choose_move(new_game("chess_engine", MIDDLEGAME))
    assert searcher.last_info["extended"] and searcher.extensions_used == 1


def test_a_stable_move_stops_early():
    # A dama preta está solta em d5: Txd5 é óbvio desde a camada 1. Com o lance estável,
    # a busca para muito antes do teto, mesmo podendo ir 20 camadas além.
    fen = "4k3/8/8/3q4/8/8/8/3RK3 w - - 0 1"
    searcher = _budgeted(depth=3, move_time=20.0, stable_fraction=0.001, stable_depths=2)
    searcher.config.extra_depth = 20
    state = new_game("chess_engine", fen)
    assert state.uci(searcher.choose_move(state)) == "d1d5"
    assert searcher.last_info["stop"] == "lance estável"
    assert searcher.last_info["seconds"] < 5


def test_a_single_legal_move_is_played_at_once():
    fen = "6rk/8/8/8/8/8/8/7K w - - 0 1"  # a torre cobre g1 e g2: só Rh2
    state = new_game("python-chess", fen)
    assert len(state.legal_moves()) == 1, fen
    searcher = _budgeted(move_time=20.0)
    t = time.monotonic()
    move = searcher.choose_move(state)
    assert move in state.legal_moves() and time.monotonic() - t < 1
    assert searcher.last_info["stop"] == "lance único" and searcher.last_score is not None


def test_the_clock_shrinks_both_caps():
    searcher = _budgeted(move_time=20.0, extended_time=40.0)
    assert searcher.caps() == (20.0, 40.0)
    searcher.clock = (100.0, 2.0)  # 100 s restantes, 2 s de incremento
    assert searcher.caps() == pytest.approx((100 / 25 + 1.5, 100 / 8))
    searcher.clock = (1000.0, 0.0)
    assert searcher.caps() == (20.0, 40.0)


def test_player_takes_the_lichess_clock_and_resets_credits(monkeypatch):
    for var in ("LUNA_DEPTH", "LUNA_TIME_LIMIT", "LUNA_EXTENDED_TIME", "LUNA_EXTENSIONS"):
        monkeypatch.delenv(var, raising=False)
    player = official_factory()
    player.set_clock(60_000, 1_000)
    assert player.searcher.clock == (60.0, 1.0)
    player.searcher.extensions_used = 3
    player.new_game()
    assert player.searcher.extensions_used == 0 and player.searcher.clock is None
