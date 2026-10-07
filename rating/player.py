"""Interface mínima que qualquer jogador (Luna, Stockfish, aleatório...) precisa cumprir.

A troca de informação é feita só com strings padrão do xadrez:
  - posição em FEN;
  - lances em UCI (ex.: "e2e4", "e7e8q").
Assim os pacotes ``rating`` e ``lichess_bot`` não dependem da implementação
interna do motor de xadrez nem da Luna; basta um adaptador fino.
"""

from __future__ import annotations

import random
from typing import Callable, Protocol, Sequence, runtime_checkable


@runtime_checkable
class MovePlayer(Protocol):
    """Qualquer objeto com ``choose_move`` serve como jogador."""

    def choose_move(self, fen: str, legal_moves: Sequence[str]) -> str:
        """Recebe a posição (FEN) e os lances legais (UCI) e devolve um deles."""
        ...


#: Fábrica de jogadores. Precisa ser uma função de nível de módulo
#: (serializável com pickle) para rodar partidas em processos paralelos.
PlayerFactory = Callable[[], MovePlayer]


class FunctionPlayer:
    """Adapta uma função ``f(fen, legal_moves) -> uci`` para ``MovePlayer``."""

    def __init__(self, fn: Callable[[str, Sequence[str]], str]):
        self._fn = fn

    def choose_move(self, fen: str, legal_moves: Sequence[str]) -> str:
        return self._fn(fen, legal_moves)


class RandomPlayer:
    """Jogador de referência que escolhe lances ao acaso (útil em testes)."""

    def __init__(self, seed: int | None = None):
        self._rng = random.Random(seed)

    def choose_move(self, fen: str, legal_moves: Sequence[str]) -> str:
        return self._rng.choice(list(legal_moves))


def random_player_factory() -> MovePlayer:
    return RandomPlayer()


def load_factory(spec: str) -> PlayerFactory:
    """Carrega uma fábrica a partir de ``"pacote.modulo:funcao"``.

    Exemplo: ``load_factory("rating.player:random_player_factory")``.
    """
    import importlib

    module_name, sep, attr = spec.partition(":")
    if not sep or not module_name or not attr:
        raise ValueError(f"Use o formato 'modulo:funcao', recebido {spec!r}")
    factory = getattr(importlib.import_module(module_name), attr)
    if not callable(factory):
        raise TypeError(f"{spec!r} não é chamável")
    return factory
