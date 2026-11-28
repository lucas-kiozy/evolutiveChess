"""Primeiro lance fixo e ruído pequeno no Lichess (pedido do Lucas em 2026-11-27)."""

import chess

from luna.player import FIRST_MOVES, LICHESS_NOISE, lichess_factory, official_factory

START = chess.STARTING_FEN


def _clean_env(monkeypatch):
    for var in ("LUNA_DEPTH", "LUNA_TIME_LIMIT", "LUNA_NOISE", "LUNA_SEED", "LUNA_VERSION"):
        monkeypatch.delenv(var, raising=False)


def _legal(board):
    return [m.uci() for m in board.legal_moves]


def test_first_move_is_e4_with_white_and_c6_with_black(monkeypatch):
    _clean_env(monkeypatch)
    assert FIRST_MOVES == {"white": "e2e4", "black": "c7c6"}
    player = official_factory()
    board = chess.Board()
    assert player.choose_move(board.fen(), _legal(board)) == "e2e4"
    for first in ("e2e4", "d2d4", "g1f3"):
        player = official_factory()
        board = chess.Board()
        board.push_uci(first)
        assert player.choose_move(board.fen(), _legal(board)) == "c7c6"


def test_the_fixed_move_keeps_the_game_history(monkeypatch):
    _clean_env(monkeypatch)
    monkeypatch.setenv("LUNA_DEPTH", "1")
    monkeypatch.setenv("LUNA_TIME_LIMIT", "0")
    player = official_factory()
    board = chess.Board()
    board.push_uci(player.choose_move(board.fen(), _legal(board)))
    board.push_uci("c7c5")
    move = player.choose_move(board.fen(), _legal(board))
    assert move in _legal(board) and player._state.ply == 3  # seguiu a mesma partida


def test_no_fixed_move_outside_the_start_position(monkeypatch):
    _clean_env(monkeypatch)
    monkeypatch.setenv("LUNA_DEPTH", "1")
    monkeypatch.setenv("LUNA_TIME_LIMIT", "0")
    board = chess.Board("rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2")
    move = official_factory().choose_move(board.fen(), _legal(board))
    assert move in _legal(board)


def test_rating_player_has_no_noise_and_lichess_player_has_a_little(monkeypatch):
    _clean_env(monkeypatch)
    assert official_factory().searcher.config.noise == 0.0
    assert lichess_factory().searcher.config.noise == LICHESS_NOISE == 2.5
    monkeypatch.setenv("LUNA_NOISE", "0")
    assert lichess_factory().searcher.config.noise == 0.0


def test_noise_only_picks_among_nearly_equal_moves(monkeypatch):
    # Com ±2,5 cp, perder material (centenas de centipeões) nunca é sorteado.
    _clean_env(monkeypatch)
    monkeypatch.setenv("LUNA_DEPTH", "2")
    monkeypatch.setenv("LUNA_TIME_LIMIT", "0")
    board = chess.Board("4k3/8/8/3q4/8/8/8/3RK3 w - - 0 1")
    for seed in range(5):
        monkeypatch.setenv("LUNA_SEED", str(seed))
        assert lichess_factory().choose_move(board.fen(), _legal(board)) == "d1d5"
