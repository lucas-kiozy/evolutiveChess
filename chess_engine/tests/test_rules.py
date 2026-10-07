"""Testes das regras e da API do motor, posição por posição."""

import random

import pytest

from chess_engine import (
    BLACK, KNIGHT, QUEEN, STARTING_FEN, WHITE, Board, make_move, move_to_uci, play_game,
    square_index,
)


def push_all(board, *ucis):
    for uci in ucis:
        board.push_uci(uci)
    return board


def test_starting_position():
    board = Board()
    assert board.fen() == STARTING_FEN
    assert len(board.legal_moves()) == 20
    assert board.turn == WHITE
    assert not board.is_check()
    assert board.outcome() is None


@pytest.mark.parametrize("fen", [
    STARTING_FEN,
    "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
    "rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq c6 0 2",
    "8/8/8/8/8/8/8/K6k b - - 37 80",
])
def test_fen_roundtrip(fen):
    assert Board(fen).fen() == fen


@pytest.mark.parametrize("fen", ["", "8/8/8/8/8/8/8/8 w - - 0 1", "rnbqkbnr/pppppppp/9/8/8/8/PPPPPPPP/RNBQKBNR w"])
def test_invalid_fen(fen):
    with pytest.raises(ValueError):
        Board(fen)


def test_fools_mate():
    board = push_all(Board(), "f2f3", "e7e5", "g2g4", "d8h4")
    assert board.is_check()
    assert board.is_checkmate()
    outcome = board.outcome()
    assert outcome.winner == BLACK
    assert outcome.termination == "checkmate"
    assert outcome.result() == "0-1"
    assert board.moves_made(BLACK) == 2
    assert board.moves_made(WHITE) == 2
    assert board.checks_given(BLACK) == 1
    assert board.checks_given(WHITE) == 0


def test_checks_counter_follows_pop():
    board = push_all(Board(), "e2e4", "f7f6", "d1h5")
    assert board.checks_given(WHITE) == 1
    board.pop()
    assert board.checks_given(WHITE) == 0
    assert board.moves_made(WHITE) == 1


def test_stalemate():
    board = Board("7k/5Q2/6K1/8/8/8/8/8 b - - 0 1")
    assert board.is_stalemate()
    assert not board.is_checkmate()
    assert board.outcome().termination == "stalemate"
    assert board.outcome().winner is None


@pytest.mark.parametrize("fen,insufficient", [
    ("8/8/8/4k3/8/8/8/4K3 w - - 0 1", True),     # K x K
    ("8/8/8/4k3/8/8/8/4KB2 w - - 0 1", True),    # K+B x K
    ("8/8/8/4k3/8/8/8/4KN2 w - - 0 1", True),    # K+N x K
    ("8/8/8/1b2k3/8/8/8/4KB2 w - - 0 1", True),  # bispos na mesma cor
    ("8/8/8/2b1k3/8/8/8/4KB2 w - - 0 1", False),  # bispos em cores diferentes
    ("8/8/8/4k3/8/8/8/3NKN2 w - - 0 1", False),  # dois cavalos (mate possível)
    ("8/8/8/3nk3/8/8/8/4KN2 w - - 0 1", False),  # cavalo x cavalo (mate possível)
    ("8/8/8/4k3/8/8/4P3/4K3 w - - 0 1", False),  # peão
    ("8/8/8/4k3/8/8/8/4KR2 w - - 0 1", False),   # torre
])
def test_insufficient_material(fen, insufficient):
    board = Board(fen)
    assert board.is_insufficient_material() is insufficient
    if insufficient:
        assert board.outcome().termination == "insufficient_material"


def test_fifty_and_seventyfive_moves():
    board = Board("8/8/8/4k3/8/8/4R3/4K3 w - - 99 80")
    assert not board.is_fifty_moves()
    board.push_uci("e2a2")
    assert board.is_fifty_moves()
    assert board.outcome().termination == "fifty_moves"
    assert board.outcome(claim_draw=False) is None
    board = Board("8/8/8/4k3/8/8/4R3/4K3 w - - 149 80")
    board.push_uci("e2a2")
    assert board.outcome(claim_draw=False).termination == "seventyfive_moves"


def test_pawn_move_and_capture_reset_halfmove_clock():
    board = Board("4k3/8/8/3p4/4P3/8/8/4K3 w - - 40 60")
    board.push_uci("e4d5")
    assert board.halfmove_clock == 0
    board.pop()
    assert board.halfmove_clock == 40


def test_threefold_and_fivefold_repetition():
    board = Board()
    shuffle = ["g1f3", "g8f6", "f3g1", "f6g8"]
    push_all(board, *shuffle)
    assert not board.is_threefold_repetition()
    assert board.repetitions() == 2
    push_all(board, *shuffle)
    assert board.repetitions() == 3
    assert board.is_threefold_repetition()
    assert board.outcome().termination == "threefold_repetition"
    assert board.outcome(claim_draw=False) is None
    push_all(board, *shuffle, *shuffle)
    assert board.is_fivefold_repetition()
    assert board.outcome(claim_draw=False).termination == "fivefold_repetition"


def test_repetition_requires_same_castling_rights():
    board = Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    # O rei sai e volta: mesmas peças, mas sem direito de roque, então não repete.
    push_all(board, "e1f1", "e8f8", "f1e1", "f8e8", "e1f1", "e8f8", "f1e1", "f8e8")
    assert not board.is_threefold_repetition()


def test_en_passant():
    board = push_all(Board(), "e2e4", "a7a6", "e4e5", "d7d5")
    assert board.ep_square == square_index("d6")
    move = board.parse_uci("e5d6")
    assert board.is_capture(move)
    board.push(move)
    assert board.piece_at(square_index("d5")) == 0
    assert board.san(board.pop()) == "exd6"
    assert board.piece_at(square_index("d5")) != 0


def test_en_passant_only_immediately():
    board = push_all(Board(), "e2e4", "a7a6", "e4e5", "d7d5", "h2h3", "h7h6")
    assert "e5d6" not in [move_to_uci(m) for m in board.legal_moves()]


def test_en_passant_horizontal_pin():
    # Capturar en passant tiraria os dois peões da 5ª fileira e exporia o rei à torre.
    board = Board("8/8/8/KPp4r/8/8/8/7k w - c6 0 1")
    assert "b5c6" not in [move_to_uci(m) for m in board.legal_moves()]


def test_castling_both_sides_and_undo():
    fen = "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1"
    board = Board(fen)
    ucis = [move_to_uci(m) for m in board.legal_moves()]
    assert "e1g1" in ucis and "e1c1" in ucis
    assert board.san(board.parse_uci("e1g1")) == "O-O"
    assert board.san(board.parse_uci("e1c1")) == "O-O-O"
    board.push_uci("e1g1")
    assert board.piece_at(square_index("f1")) > 0 and board.piece_at(square_index("h1")) == 0
    assert board.fen().split()[2] == "kq"
    board.pop()
    assert board.fen() == fen


@pytest.mark.parametrize("fen,forbidden", [
    ("r3k2r/8/8/8/8/8/8/R3K2R w - - 0 1", ["e1g1", "e1c1"]),           # sem direitos
    ("r3k2r/8/8/8/8/8/8/R3K1NR w KQkq - 0 1", ["e1g1"]),               # casa ocupada
    ("r3k2r/8/8/8/8/8/8/RN2K2R w KQkq - 0 1", ["e1c1"]),               # b1 ocupada
    ("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1", []),
    ("r3k2r/8/8/8/4r3/8/8/R3K2R w KQkq - 0 1", ["e1g1", "e1c1"]),      # em xeque
    ("r3k2r/8/8/8/5r2/8/8/R3K2R w KQkq - 0 1", ["e1g1"]),              # passa por f1 atacada
    ("r3k2r/8/8/8/6r1/8/8/R3K2R w KQkq - 0 1", ["e1g1"]),              # chega em g1 atacada
    ("r3k2r/8/8/8/3r4/8/8/R3K2R w KQkq - 0 1", ["e1c1"]),              # passa por d1 atacada
])
def test_castling_restrictions(fen, forbidden):
    ucis = [move_to_uci(m) for m in Board(fen).legal_moves()]
    for uci in forbidden:
        assert uci not in ucis
    for uci in {"e1g1", "e1c1"} - set(forbidden):
        assert uci in ucis


def test_castling_allowed_when_only_b1_attacked():
    board = Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    board.squares[square_index("b8")] = -4  # torre preta atacando b1
    board.squares[square_index("a8")] = 0
    board.castling &= ~8
    board._legal = None
    assert "e1c1" in [move_to_uci(m) for m in board.legal_moves()]


def test_capturing_rook_removes_castling_right():
    board = Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    board.push_uci("a1a8")
    assert board.fen().split()[2] == "Kk"


def test_promotion():
    board = Board("8/P6k/8/8/8/8/8/K7 w - - 0 1")
    promos = sorted(move_to_uci(m) for m in board.legal_moves() if m >> 12)
    assert promos == ["a7a8b", "a7a8n", "a7a8q", "a7a8r"]
    board.push(make_move(square_index("a7"), square_index("a8"), KNIGHT))
    assert board.piece_at(square_index("a8")) == KNIGHT
    board.pop()
    board.push_uci("a7a8q")
    assert board.piece_at(square_index("a8")) == QUEEN
    assert board.san(board.pop()) == "a8=Q"


def test_pinned_piece_cannot_leave_line():
    board = Board("4k3/4r3/8/8/8/8/4B3/4K3 w - - 0 1")
    assert all(m & 63 != square_index("e2") for m in board.legal_moves())


def test_must_answer_check():
    board = Board("4k3/8/8/8/8/8/3PPP2/r3K3 w - - 0 1")
    assert sorted(move_to_uci(m) for m in board.legal_moves()) == []
    assert board.is_checkmate()


def test_san_disambiguation_and_parse():
    board = Board("4k3/8/8/8/8/8/4K3/R6R w - - 0 1")
    assert board.san(board.parse_uci("a1d1")) == "Rad1"
    assert board.san(board.parse_uci("h1f1")) == "Rhf1"
    assert board.san(board.parse_uci("a1a5")) == "Ra5"
    board = Board("4k3/8/8/8/R7/8/8/R3K3 w Q - 0 1")
    assert board.san(board.parse_uci("a1a2")) == "R1a2"
    assert board.parse_san("R4a2") == board.parse_uci("a4a2")
    board = Board()
    assert board.push_san("e4") == board.peek()
    board.push_san("e5")
    board.push_san("Nf3")
    assert move_to_uci(board.peek()) == "g1f3"
    with pytest.raises(ValueError):
        board.parse_san("Ke3")


def test_san_check_and_mate_suffix():
    board = push_all(Board(), "f2f3", "e7e5", "g2g4")
    assert board.san(board.parse_uci("d8h4")) == "Qh4#"
    board = push_all(Board(), "e2e4", "f7f6")
    assert board.san(board.parse_uci("d1h5")) == "Qh5+"


@pytest.mark.parametrize("uci", ["e2e5", "e7e5", "zz", "e2e4q", "e1g1"])
def test_parse_uci_rejects_illegal(uci):
    with pytest.raises(ValueError):
        Board().parse_uci(uci)


def test_copy_is_independent():
    board = push_all(Board(), "e2e4")
    clone = board.copy()
    clone.push_uci("e7e5")
    assert board.fen() != clone.fen()
    assert board.ply == 1 and clone.ply == 2
    clone.pop()
    assert clone.fen() == board.fen()


def test_push_pop_restores_everything():
    rng = random.Random(1)
    board = Board()
    fens, keys = [board.fen()], [board.key()]
    for _ in range(200):
        if board.is_game_over():
            break
        board.push(rng.choice(board.legal_moves()))
        fens.append(board.fen())
        keys.append(board.key())
        assert board.key() == Board(board.fen())._compute_hash() or board.ep_square >= 0
    while board.ply:
        assert board.fen() == fens.pop()
        assert board.key() == keys.pop()
        board.pop()
    assert board.fen() == STARTING_FEN


def test_incremental_hash_matches_fresh_hash():
    rng = random.Random(7)
    for _ in range(20):
        board = Board()
        for _ in range(120):
            if board.is_game_over():
                break
            board.push(rng.choice(board.legal_moves()))
            assert board.key() == Board(board.fen()).key()


def test_play_game_with_random_players():
    rng = random.Random(3)

    def player(board):
        return rng.choice(board.legal_moves())

    for _ in range(10):
        result = play_game(player, player)
        assert result.outcome is not None
        assert result.plies == result.white_moves + result.black_moves
        assert result.white_moves - result.black_moves in (0, 1)
        replay = Board()
        for uci in result.moves:
            replay.push_uci(uci)
        assert replay.fen() == result.final_fen
        assert replay.checks_given(WHITE) == result.white_checks
        assert replay.checks_given(BLACK) == result.black_checks
        if result.outcome.termination == "checkmate":
            assert result.checks_by(result.winner) >= 1


def test_play_game_max_plies():
    result = play_game(lambda b: b.legal_moves()[0], lambda b: b.legal_moves()[0], max_plies=10)
    assert result.plies <= 10
