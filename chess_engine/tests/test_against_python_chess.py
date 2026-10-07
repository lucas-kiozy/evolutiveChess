"""Compara o motor com a biblioteca python-chess (usada só como oráculo de teste).

Joga partidas aleatórias e, em cada posição, confere lances legais, xeque, FEN,
SAN e o resultado. Pulado se ``chess`` (python-chess) não estiver instalado.
Ajuste a quantidade de partidas com ``CHESS_ORACLE_GAMES`` (padrão 60).
"""

import os
import random

import pytest

from chess_engine import Board, move_to_uci

chess = pytest.importorskip("chess")

GAMES = int(os.environ.get("CHESS_ORACLE_GAMES", "60"))

TERMINATIONS = {
    "CHECKMATE": "checkmate",
    "STALEMATE": "stalemate",
    "INSUFFICIENT_MATERIAL": "insufficient_material",
    "SEVENTYFIVE_MOVES": "seventyfive_moves",
    "FIVEFOLD_REPETITION": "fivefold_repetition",
}


def compare(ours, theirs):
    our_moves = {move_to_uci(m): m for m in ours.legal_moves()}
    their_moves = {m.uci(): m for m in theirs.legal_moves}
    assert set(our_moves) == set(their_moves), ours.fen()
    assert ours.is_check() == theirs.is_check(), ours.fen()
    assert ours.fen() == theirs.fen(en_passant="fen"), ours.fen()
    assert ours.is_insufficient_material() == theirs.is_insufficient_material(), ours.fen()
    for uci, move in our_moves.items():
        assert ours.san(move) == theirs.san(their_moves[uci]), (ours.fen(), uci)
    expected = theirs.outcome(claim_draw=False)
    got = ours.outcome(claim_draw=False)
    if expected is None:
        assert got is None, ours.fen()
    else:
        assert got is not None, ours.fen()
        assert got.termination == TERMINATIONS[expected.termination.name], ours.fen()
        winner = None if expected.winner is None else (1 if expected.winner else -1)
        assert got.winner == winner


@pytest.mark.parametrize("seed", range(GAMES))
def test_random_game_matches_python_chess(seed):
    rng = random.Random(seed)
    ours, theirs = Board(), chess.Board()
    while True:
        compare(ours, theirs)
        if ours.outcome(claim_draw=False) is not None:
            break
        moves = ours.legal_moves()
        # Prefere capturas e promoções às vezes, para chegar a finais variados.
        tactical = [m for m in moves if ours.is_capture(m) or m >> 12]
        move = rng.choice(tactical if tactical and rng.random() < 0.5 else moves)
        uci = move_to_uci(move)
        ours.push(move)
        theirs.push_uci(uci)
    # Desfaz tudo e confere de volta.
    while ours.ply:
        ours.pop()
        theirs.pop()
        assert ours.fen() == theirs.fen(en_passant="fen")


@pytest.mark.parametrize("fen", [
    "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
    "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1",
    "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
])
def test_random_games_from_tricky_positions(fen):
    rng = random.Random(fen)
    for _ in range(10):
        ours, theirs = Board(fen), chess.Board(fen)
        for _ in range(80):
            compare(ours, theirs)
            if ours.outcome(claim_draw=False) is not None:
                break
            move = rng.choice(ours.legal_moves())
            ours.push(move)
            theirs.push_uci(move_to_uci(move))
