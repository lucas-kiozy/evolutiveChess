"""Adaptador provisório sobre a biblioteca python-chess.

Fica atrás de ``luna.game_interface.GameState`` para ser trocado pelo motor
próprio do projeto (``chess_engine``) sem mexer no resto da Luna.
"""

from __future__ import annotations

from typing import Iterable, Optional

import chess

from luna.game_interface import Outcome

_SYMBOL = {
    chess.PAWN: "P",
    chess.KNIGHT: "N",
    chess.BISHOP: "B",
    chess.ROOK: "R",
    chess.QUEEN: "Q",
    chess.KING: "K",
}

_TERMINATION = {
    chess.Termination.CHECKMATE: "checkmate",
    chess.Termination.STALEMATE: "stalemate",
    chess.Termination.INSUFFICIENT_MATERIAL: "insufficient_material",
    chess.Termination.SEVENTYFIVE_MOVES: "seventyfive_moves",
    chess.Termination.FIVEFOLD_REPETITION: "fivefold_repetition",
    chess.Termination.FIFTY_MOVES: "fifty_moves",
    chess.Termination.THREEFOLD_REPETITION: "threefold_repetition",
}


class PythonChessGame:
    __slots__ = ("_board",)

    def __init__(self, fen: Optional[str] = None, _board: Optional[chess.Board] = None):
        if _board is not None:
            self._board = _board
        else:
            self._board = chess.Board(fen) if fen else chess.Board()

    @property
    def white_to_move(self) -> bool:
        return self._board.turn == chess.WHITE

    @property
    def ply(self) -> int:
        return self._board.ply()

    def legal_moves(self) -> list[str]:
        return [m.uci() for m in self._board.legal_moves]

    def push(self, move: str) -> None:
        self._board.push(chess.Move.from_uci(move))

    def pop(self) -> str:
        return self._board.pop().uci()

    def copy(self) -> "PythonChessGame":
        return PythonChessGame(_board=self._board.copy(stack=True))

    def is_check(self) -> bool:
        return self._board.is_check()

    def is_checkmate(self) -> bool:
        return self._board.is_checkmate()

    def is_capture(self, move: str) -> bool:
        return self._board.is_capture(chess.Move.from_uci(move))

    def captured_piece(self, move: str) -> Optional[str]:
        m = chess.Move.from_uci(move)
        if self._board.is_en_passant(m):
            return "P"
        piece = self._board.piece_at(m.to_square)
        return _SYMBOL[piece.piece_type] if piece else None

    def moving_piece(self, move: str) -> str:
        piece = self._board.piece_at(chess.Move.from_uci(move).from_square)
        return _SYMBOL[piece.piece_type] if piece else "?"

    def is_promotion(self, move: str) -> bool:
        return len(move) == 5

    def gives_check(self, move: str) -> bool:
        return self._board.gives_check(chess.Move.from_uci(move))

    def is_repetition(self) -> bool:
        return self._board.is_repetition(2)

    def outcome(self, claim_draw: bool = True) -> Optional[Outcome]:
        result = self._board.outcome(claim_draw=claim_draw)
        if result is None:
            return None
        return Outcome(winner=result.winner, termination=_TERMINATION[result.termination])

    def pieces(self) -> Iterable[tuple[int, str, bool]]:
        for square, piece in self._board.piece_map().items():
            yield square, _SYMBOL[piece.piece_type], piece.color == chess.WHITE

    def mobility(self, white: bool) -> int:
        board = self._board
        color = chess.WHITE if white else chess.BLACK
        own = board.occupied_co[color]
        total = 0
        for square in chess.scan_forward(own & ~board.pawns & ~board.kings):
            total += chess.popcount(board.attacks_mask(square) & ~own)
        return total

    def fen(self) -> str:
        return self._board.fen()
