"""Adaptador para o motor próprio do projeto (pacote ``chess_engine``).

Lances são os inteiros do motor (``origem | destino << 6 | promocao << 12``);
a Luna só os converte para UCI ao guardar a partida.
"""

from __future__ import annotations

from typing import Iterable, Optional

from chess_engine import BLACK, WHITE, Board, move_to_uci
from chess_engine.tables import KNIGHT_ATTACKS, RAYS
from luna.game_interface import Outcome

_SYMBOL = {1: "P", 2: "N", 3: "B", 4: "R", 5: "Q", 6: "K"}
_KNIGHT, _BISHOP, _ROOK, _QUEEN, _KING = 2, 3, 4, 5, 6
_DIAGONAL = (4, 5, 6, 7)
_ORTHOGONAL = (0, 1, 2, 3)


class ChessEngineGame:
    __slots__ = ("_board",)

    def __init__(self, fen: Optional[str] = None, _board: Optional[Board] = None):
        if _board is not None:
            self._board = _board
        else:
            self._board = Board(fen) if fen else Board()

    @property
    def white_to_move(self) -> bool:
        return self._board.turn == WHITE

    @property
    def ply(self) -> int:
        return self._board.ply

    def legal_moves(self) -> list[int]:
        return self._board.legal_moves()

    def push(self, move: int) -> None:
        self._board.push(move)

    def pop(self) -> int:
        return self._board.pop()

    def uci(self, move: int) -> str:
        return move_to_uci(move)

    def parse_uci(self, text: str) -> int:
        return self._board.parse_uci(text)

    def san(self, move: int) -> str:
        return self._board.san(move)

    def copy(self) -> "ChessEngineGame":
        return ChessEngineGame(_board=self._board.copy())

    def is_check(self) -> bool:
        return self._board.is_check()

    def is_checkmate(self) -> bool:
        return self._board.is_checkmate()

    def is_capture(self, move: int) -> bool:
        return self._board.is_capture(move)

    def captured_piece(self, move: int) -> Optional[str]:
        piece = self._board.squares[(move >> 6) & 63]
        if piece:
            return _SYMBOL[abs(piece)]
        return "P" if self._board.is_capture(move) else None  # en passant

    def moving_piece(self, move: int) -> str:
        piece = self._board.squares[move & 63]
        return _SYMBOL[abs(piece)] if piece else "?"

    def is_promotion(self, move: int) -> bool:
        return move >> 12 != 0

    def gives_check(self, move: int) -> bool:
        return self._board.gives_check(move)

    def is_repetition(self) -> bool:
        return self._board.repetitions() >= 2

    def outcome(self, claim_draw: bool = True) -> Optional[Outcome]:
        result = self._board.outcome(claim_draw=claim_draw)
        if result is None:
            return None
        winner = None if result.winner is None else result.winner == WHITE
        return Outcome(winner=winner, termination=result.termination)

    def pieces(self) -> Iterable[tuple[int, str, bool]]:
        for square, piece in enumerate(self._board.squares):
            if piece:
                yield square, _SYMBOL[abs(piece)], piece > 0

    def mobility(self, white: bool) -> int:
        squares = self._board.squares
        color = WHITE if white else BLACK
        total = 0
        for sq, piece in enumerate(squares):
            if piece * color <= 1:  # vazio, adversária ou peão
                continue
            kind = abs(piece)
            if kind == _KING:
                continue
            if kind == _KNIGHT:
                for t in KNIGHT_ATTACKS[sq]:
                    if squares[t] * color <= 0:
                        total += 1
                continue
            if kind == _BISHOP:
                directions = _DIAGONAL
            elif kind == _ROOK:
                directions = _ORTHOGONAL
            else:
                directions = _ORTHOGONAL + _DIAGONAL
            for d in directions:
                for t in RAYS[d][sq]:
                    p = squares[t]
                    if p * color <= 0:
                        total += 1
                    if p:
                        break
        return total

    def fen(self) -> str:
        return self._board.fen()
