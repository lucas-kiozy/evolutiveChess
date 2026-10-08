import random

import chess
import pytest

from lichess_bot.game import GameRunner
from lichess_bot.learning import build_record
from lichess_bot.pacing import MovePacing, NoPacing
from lichess_bot.tests.test_lichess_bot import FakeClient, full
from rating.match import play_game
from rating.player import FunctionPlayer, RandomPlayer
from rating.resign import (
    ResignPolicy,
    forced_draw_available,
    material_balance,
    score_after,
    wants_to_resign,
)

# Brancas só com o rei contra rei e dama pretos: brancas 9 pontos atrás.
LOST_FOR_WHITE = "4k3/8/8/8/8/8/3q4/K7 w - - 0 1"


# ----------------------------------------------------------------- ritmo
def test_pacing_ranges_follow_lucas_rule():
    p = MovePacing(rng=random.Random(1))
    assert all(p.target_seconds(n) == 20 for n in range(1, 7))
    middle = {p.target_seconds(n) for n in range(7, 41) for _ in range(20)}
    assert middle <= set(range(1, 17)) and min(middle) == 1 and max(middle) == 16
    late = {p.target_seconds(n) for n in range(41, 120) for _ in range(5)}
    assert late <= set(range(16, 91)) and min(late) == 16 and max(late) == 90
    assert all(float(x).is_integer() for x in middle | late)


def test_pacing_respects_the_clock():
    p = MovePacing(rng=random.Random(1))
    # 60 s no relógio, sem incremento: no máximo 8% = 4,8 s
    assert p.seconds_for(1, remaining_ms=60_000, increment_ms=0) == pytest.approx(4.8)
    # relógio folgado: vale a regra
    assert p.seconds_for(1, remaining_ms=1_800_000, increment_ms=20_000) == 20
    assert p.seconds_for(1) == 20  # sem relógio conhecido
    with pytest.raises(ValueError):
        p.target_seconds(0)


def test_no_pacing_is_zero():
    assert NoPacing().seconds_for(50, 1000, 0) == 0


class FakeTime:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def clock(self):
        return self.now

    def sleep(self, s):
        self.sleeps.append(s)
        self.now += s


def test_runner_waits_total_time_including_thinking():
    t = FakeTime()

    def think(fen, legal):
        t.now += 3  # pensou 3 s
        return "e2e4"

    end = {"type": "gameState", "moves": "e2e4", "status": "resign", "winner": "white"}
    start = full("")
    start["state"].update(wtime=1_800_000, winc=20_000)  # 30+20
    client = FakeClient([start, end])
    p = MovePacing(rng=random.Random(0))
    runner = GameRunner(
        client, FunctionPlayer(think), "g1", "luna", pacing=p, sleep=t.sleep, clock=t.clock
    )
    runner.run()
    assert client.moves == ["e2e4"]
    assert t.sleeps == [pytest.approx(17)]  # 20 s no total


def test_runner_speeds_up_on_a_short_clock():
    t = FakeTime()
    end = {"type": "gameState", "moves": "e2e4", "status": "resign", "winner": "white"}
    client = FakeClient([full(""), end])  # 60 s no relógio, sem incremento
    runner = GameRunner(
        client,
        FunctionPlayer(lambda fen, legal: "e2e4"),
        "g1",
        "luna",
        pacing=MovePacing(),
        sleep=t.sleep,
        clock=t.clock,
    )
    runner.run()
    assert t.sleeps == [pytest.approx(4.8)]  # 8% de 60 s, não 20 s


def test_runner_counts_luna_moves_as_black():
    events = [full("e2e4 e7e5 g1f3 b8c6 f1c4 g8f6 d2d3", white="opp", black="luna")]
    client = FakeClient(events + [{"type": "gameState", "moves": "x", "status": "draw"}])
    runner = GameRunner(client, FunctionPlayer(lambda fen, legal: legal[0]), "g1", "luna")
    runner._on_full(events[0])
    board = chess.Board()
    for m in "e2e4 e7e5 g1f3 b8c6 f1c4 g8f6 d2d3".split():
        board.push_uci(m)
    assert runner._luna_move_number(board) == 4


# ------------------------------------------------------------ desistência
def test_material_balance():
    assert material_balance(chess.Board(), chess.WHITE) == 0
    assert material_balance(chess.Board(LOST_FOR_WHITE), chess.WHITE) == -9


def test_policy_needs_three_moves_in_a_row():
    pol = ResignPolicy()  # -1000 cp, 3 lances, como no lichess-bot
    assert [pol.update(-1200) for _ in range(3)] == [False, False, True]
    pol.new_game()
    assert not pol.update(-99_000)  # mate contra: conta, mas ainda é o 1º
    pol.update(-1000)
    assert not pol.update(-200)  # melhorou: zera a contagem
    assert not pol.update(-1500)


def test_score_comes_from_player_or_material():
    class Scored:
        last_score = -1234

    assert score_after(Scored(), chess.STARTING_FEN, "e2e4") == -1234
    # sem last_score: material depois do lance (dama a menos = -900)
    assert score_after(object(), LOST_FOR_WHITE, "a1b1") == -900


class Hopeless:
    last_score = -5000

    def choose_move(self, fen, legal):
        return legal[0]


def test_player_own_rule_wins():
    class P:
        def should_resign(self, fen):
            return True

    assert wants_to_resign(P(), None, chess.Board(), "e2e4")
    assert not wants_to_resign(object(), None, chess.Board(LOST_FOR_WHITE), "a1b1")


# Brancas com muito menos material, mas com xeque perpétuo: Qe8+ Kh7 Qh5+ Kg8...
PERPETUAL = "6k1/6p1/8/7Q/8/7K/r7/q7 w - - 0 1"


def test_forced_draw_detects_perpetual_check():
    assert forced_draw_available(chess.Board(PERPETUAL))
    assert not forced_draw_available(chess.Board(LOST_FOR_WHITE))
    assert not forced_draw_available(chess.Board())


def test_forced_draw_detects_capture_to_bare_kings_and_history():
    assert forced_draw_available(chess.Board("8/8/8/8/8/8/1n6/K6k w - - 0 1"))
    board = chess.Board()
    for uci in ["g1f3", "g8f6", "f3g1", "f6g8"] * 2:
        board.push_uci(uci)
    assert forced_draw_available(board)  # a posição inicial já apareceu 3 vezes


def test_forced_draw_gives_up_safely_on_budget():
    assert forced_draw_available(chess.Board(PERPETUAL), max_nodes=1)


def test_no_resign_while_a_forced_draw_exists():
    pol = ResignPolicy(moves=1)
    assert not wants_to_resign(Hopeless(), pol, chess.Board(PERPETUAL), "h5e8")
    assert wants_to_resign(Hopeless(), ResignPolicy(moves=1), chess.Board(LOST_FOR_WHITE), "a1b1")


def test_runner_resigns_on_third_hopeless_move():
    states = [
        full("", white="luna", black="opp"),
        {"type": "gameState", "moves": "e2e4 e7e5", "status": "started"},
        {"type": "gameState", "moves": "e2e4 e7e5 d2d4 d7d5", "status": "started"},
        {
            "type": "gameState",
            "moves": "e2e4 e7e5 d2d4 d7d5",
            "status": "resign",
            "winner": "black",
        },
    ]
    script = iter(["e2e4", "d2d4", "g1f3"])

    class P(Hopeless):
        def choose_move(self, fen, legal):
            return next(script)

    client = FakeClient(states)
    client.resigned = []
    client.resign = lambda gid: client.resigned.append(gid)
    rec = GameRunner(client, P(), "g1", "luna", resign_policy=ResignPolicy()).run()
    assert client.moves == ["e2e4", "d2d4"]  # o 3º lance vira desistência
    assert client.resigned == ["g1"]
    assert rec.luna_resigned and rec.luna_score == 0.0


def test_opponent_resignation_is_a_full_point():
    rec = build_record("x", "white", ["e2e4"], "resign", "white")
    assert rec.luna_won_by_resignation and rec.luna_score == 1.0
    assert not rec.luna_won_by_mate and not rec.luna_resigned


def test_play_game_resignation_loses_for_who_resigns():
    res = play_game(
        Hopeless(),
        RandomPlayer(1),
        resign={chess.WHITE: ResignPolicy(moves=1)},
    )
    assert res.result == "0-1" and res.termination == "resignation"
    assert res.score_for(chess.BLACK) == 1.0


def test_no_resign_when_opponent_cannot_mate():
    # Brancas sem nada; pretas só com rei e cavalo: não há como perder.
    assert forced_draw_available(chess.Board("4k3/8/8/8/8/8/3n4/K7 w - - 0 1"))


def test_player_seeing_a_draw_blocks_resignation():
    class SeesDraw(Hopeless):
        def sees_forced_draw(self):
            return True

    board = chess.Board(LOST_FOR_WHITE)
    assert not wants_to_resign(SeesDraw(), ResignPolicy(moves=1), board, "a1b1")
