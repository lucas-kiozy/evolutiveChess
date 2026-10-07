"""Motor de xadrez em Python puro, com todas as regras (roque, en passant,
promoção, xeque-mate, afogamento e empates por material, 50/75 lances e repetição).

Uso rápido::

    from chess_engine import Board, move_to_uci

    board = Board()
    while not board.is_game_over():
        move = board.legal_moves()[0]
        board.push(move)
    print(board.outcome().result(), board.moves_made(1), board.checks_given(1))

Veja ``chess_engine/API.md`` para a interface completa.
"""

from .board import (
    PROMOTION_PIECES, STARTING_FEN, Board, Outcome, make_move, move_from, move_promotion,
    move_to, move_to_uci, perft,
)
from .game import play_game
from .tables import (
    BISHOP, BLACK, EMPTY, KING, KNIGHT, PAWN, QUEEN, ROOK, SQUARE_NAMES, WHITE, square_index,
)

__all__ = [
    "Board", "Outcome", "STARTING_FEN", "PROMOTION_PIECES",
    "make_move", "move_from", "move_to", "move_promotion", "move_to_uci", "perft", "play_game",
    "WHITE", "BLACK", "EMPTY", "PAWN", "KNIGHT", "BISHOP", "ROOK", "QUEEN", "KING",
    "SQUARE_NAMES", "square_index",
]
