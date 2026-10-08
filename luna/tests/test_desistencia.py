"""Desistência da Luna e o bônus da vitória por desistência na régua de treino."""

import pytest

from luna.adapters import new_game
from luna.evolution import EvolutionConfig
from luna.fitness import RESULT_POINTS, collect_stats, rank, resign_bonus_games
from luna.genome import Genome
from luna.match import GameRecord, MatchConfig, play_game
from luna.player import LunaPlayer
from luna.ranking import bradley_terry
from luna.resign import (
    ResignTracker,
    can_force_draw,
    opponent_cannot_mate,
    sees_forced_draw,
    should_resign,
    state_from_moves,
)
from luna.search import SearchConfig

BACKENDS = ["chess_engine", "python-chess"]
# Brancas (a Luna) só com o rei contra dama e torre; com 99 meios-lances sem captura
# nem lance de peão, qualquer lance do rei permite pedir empate pelos 50 lances.
FIFTY = "k7/8/8/8/3q4/8/7r/K7 w - - 99 120"
LOST = "k7/8/8/8/3q4/8/7r/K7 w - - 0 120"
PERPETUAL = "K7/2q2rk1/3Q4/8/2r5/8/8/8 w - - 0 1"


def record(winner, termination, white="a", black="b"):
    return GameRecord(
        white_id=white,
        black_id=black,
        winner=winner,
        termination=termination,
        plies=0,
        white_checks=0,
        black_checks=0,
        mate_moves=None,
        material_balance=0,
        moves=[],
    )


# ---------------------------------------------------------------- regra


def test_tracker_needs_consecutive_lost_moves():
    t = ResignTracker()
    assert not t.update(-1200) and not t.update(-1500)
    assert not t.update(-300)  # zera a contagem
    assert not t.update(-1000) and not t.update(-1000)
    assert t.update(-5000)
    with pytest.raises(ValueError):
        ResignTracker(score=10)


@pytest.mark.parametrize("backend", BACKENDS)
def test_fifty_move_rule_is_a_forced_draw(backend):
    assert can_force_draw(new_game(backend, FIFTY))
    assert not sees_forced_draw(new_game(backend, LOST))


@pytest.mark.parametrize("backend", BACKENDS)
def test_threefold_repetition_is_a_forced_draw(backend):
    state = new_game(backend)
    for uci in ("g1f3", "g8f6", "f3g1", "f6g8") * 2:
        state.push(state.parse_uci(uci))
    assert can_force_draw(state, 1)  # Cf3 repete a posição pela terceira vez
    state = state_from_moves(["g1f3", "g8f6", "f3g1", "f6g8"], backend=backend)
    assert not can_force_draw(state, 1)  # só duas vezes ainda não é empate


@pytest.mark.parametrize("backend", BACKENDS)
def test_perpetual_check_is_a_forced_draw(backend):
    # Brancas só com a dama contra dama e duas torres, sem mate à vista: empate forçado.
    assert can_force_draw(new_game(backend, PERPETUAL), max_nodes=10**6)
    assert not can_force_draw(new_game(backend, LOST), max_nodes=10**6)


def test_draw_search_gives_up_without_resigning():
    state = new_game("python-chess")
    fen = state.fen()
    assert can_force_draw(state, max_nodes=10)  # na dúvida, não desiste
    assert state.fen() == fen and state.ply == 0  # e devolve o estado intacto


@pytest.mark.parametrize("backend", BACKENDS)
def test_opponent_without_mating_material(backend):
    assert opponent_cannot_mate(new_game(backend, "k7/8/8/8/8/8/8/K1n5 w - - 0 1"))
    assert not opponent_cannot_mate(new_game(backend, "k7/8/8/8/8/8/8/K1r5 w - - 0 1"))
    assert not opponent_cannot_mate(new_game(backend, "k7/8/8/8/8/8/8/K1nn4 w - - 0 1"))


def test_should_resign_only_without_forced_draw():
    t = ResignTracker(moves=1)
    assert not should_resign(t, -2000, new_game("python-chess", FIFTY))
    assert should_resign(t, -2000, new_game("python-chess", LOST))
    assert not should_resign(t, -10, new_game("python-chess", LOST))


# ---------------------------------------------------------------- partidas


def test_play_game_ends_by_resignation():
    cfg = MatchConfig(search=SearchConfig(depth=1), resign_score=-1.0, resign_moves=1)
    rec = play_game(Genome.reference(id="a"), Genome.reference(id="b"), cfg, seed=3)
    assert rec.termination == "resignation"
    resigned_white = rec.plies % 2 == 0  # quem desistiu era quem ia jogar
    assert rec.winner == ("black" if resigned_white else "white")
    assert rec.mate_moves is None and len(rec.moves) == rec.plies


def test_resignation_can_be_turned_off():
    cfg = MatchConfig(search=SearchConfig(depth=1), resign_score=-1.0, resign_moves=0, max_plies=30)
    rec = play_game(Genome.reference(id="a"), Genome.reference(id="b"), cfg, seed=3)
    assert rec.termination != "resignation"


def test_player_sees_forced_draw():
    player = LunaPlayer(Genome.reference(), depth=1, backend="python-chess")
    assert not player.sees_forced_draw()  # nada jogado ainda
    player.choose_move(FIFTY, ["a1b1", "a1a2"])
    assert player.sees_forced_draw()
    player.new_game()
    player.choose_move(LOST, ["a1b1", "a1a2"])
    assert not player.sees_forced_draw()


# ---------------------------------------------------------------- régua


def test_resign_win_is_worth_six_points():
    stats = collect_stats([record("white", "resignation"), record("white", "checkmate")])
    a, b = stats["a"], stats["b"]
    assert (a.wins, a.resign_wins, a.result_points) == (2, 1, 11.0)
    assert b.result_points == -2.0  # quem desiste leva a derrota de sempre
    assert a.points({**RESULT_POINTS, "resign_win": 1.0}) == 6.0


def test_regua_ranks_resign_win_above_mate():
    stats = collect_stats(
        [record("white", "resignation", "a", "x"), record("white", "checkmate", "b", "y")]
    )
    assert rank(stats)[:2] == ["a", "b"]
    assert rank(stats, {**RESULT_POINTS, "resign_win": 1.0})[0] == "b"


def test_bonus_moves_bradley_terry_strength():
    results = [("a", "c", 1.0), ("b", "c", 1.0)]
    per = resign_bonus_games()
    assert per == pytest.approx(1 / 6)
    s = bradley_terry(results, bonus={"a": per})
    assert s["a"].elo > s["b"].elo
    s = bradley_terry(results, bonus={"a": -4 / 6})
    assert s["a"].elo < s["b"].elo
    assert bradley_terry(results, bonus={}) == bradley_terry(results)


def test_evolution_config_scale():
    cfg = EvolutionConfig.from_dict({"resign_win_points": 1.0})
    assert cfg.scale["resign_win"] == 1.0 and cfg.scale["win"] == 5.0
    assert EvolutionConfig().scale["resign_win"] == 6.0
    assert EvolutionConfig().match.resign_moves == 3
