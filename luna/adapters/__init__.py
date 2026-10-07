"""Backends de regras de xadrez que implementam ``luna.game_interface.GameState``."""

from __future__ import annotations

from typing import Callable, Optional

from luna.game_interface import GameState


def _python_chess(fen: Optional[str] = None) -> GameState:
    from luna.adapters.python_chess import PythonChessGame

    return PythonChessGame(fen)


# Para plugar o motor do projeto: adicione aqui "chess_engine": _chess_engine,
# apontando para um adaptador em luna/adapters/chess_engine.py.
BACKENDS: dict[str, Callable[[Optional[str]], GameState]] = {
    "python-chess": _python_chess,
}

DEFAULT_BACKEND = "python-chess"


def new_game(backend: str = DEFAULT_BACKEND, fen: Optional[str] = None) -> GameState:
    try:
        factory = BACKENDS[backend]
    except KeyError:
        raise ValueError(
            f"Backend desconhecido: {backend!r}. Disponíveis: {sorted(BACKENDS)}"
        ) from None
    return factory(fen)
