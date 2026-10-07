"""Backends de regras de xadrez que implementam ``luna.game_interface.GameState``."""

from __future__ import annotations

from typing import Callable, Optional

from luna.game_interface import GameState


def _python_chess(fen: Optional[str] = None) -> GameState:
    from luna.adapters.python_chess import PythonChessGame

    return PythonChessGame(fen)


def _chess_engine(fen: Optional[str] = None) -> GameState:
    from luna.adapters.chess_engine import ChessEngineGame

    return ChessEngineGame(fen)


BACKENDS: dict[str, Callable[[Optional[str]], GameState]] = {
    "python-chess": _python_chess,
    "chess_engine": _chess_engine,
}

DEFAULT_BACKEND = "chess_engine"  # motor do projeto, cerca de 2x mais rápido


def new_game(backend: str = DEFAULT_BACKEND, fen: Optional[str] = None) -> GameState:
    try:
        factory = BACKENDS[backend]
    except KeyError:
        raise ValueError(
            f"Backend desconhecido: {backend!r}. Disponíveis: {sorted(BACKENDS)}"
        ) from None
    return factory(fen)
