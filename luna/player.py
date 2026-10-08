"""A Luna como jogadora das partidas que contam: rating contra o Stockfish e Lichess.

Uso: ``python -m rating ... --player luna.player:official_factory`` ou
``python -m lichess_bot play --player luna.player:official_factory``.

Duas diferenças em relação ao treino, decididas pelo Lucas com base na análise de
2026-10-08:

- **Profundidade 3** (``OFFICIAL_DEPTH``) e sem ruído. A mesma Luna em
  profundidade 3 venceu a de profundidade 2 por +319 ± 54 Elo e mediu 1663 ± 48
  contra o Stockfish, contra 1300 ± 45 em profundidade 2. O treino segue em 2.
- **Histórico da partida.** ``rating`` e ``lichess_bot`` passam só a FEN, e sem o
  histórico a busca não sabe quais posições já ocorreram: nas medições, ~4 empates
  por repetição em cada 60 partidas tinham a Luna 3 ou mais peões à frente. A
  jogadora guarda a própria partida e, a cada FEN nova, descobre qual lance o
  adversário fez; assim as repetições e o contempt voltam a funcionar. Se a FEN
  não continuar a partida guardada (outra partida, posição inicial diferente), ela
  recomeça a partir da FEN.
"""

from __future__ import annotations

import os
import random
from typing import Optional, Sequence

from luna.adapters import DEFAULT_BACKEND, new_game
from luna.game_interface import GameState
from luna.genome import Genome
from luna.promotion import OFFICIAL_DEPTH
from luna.search import SearchConfig, Searcher


def _position_key(fen: str) -> str:
    """Peças, vez e roques: o que identifica a posição para seguir a partida."""
    return " ".join(fen.split()[:3])


class LunaPlayer:
    """Cumpre ``rating.player.MovePlayer``: ``choose_move(fen, lances_uci) -> uci``."""

    def __init__(
        self,
        genome: Genome,
        depth: int = OFFICIAL_DEPTH,
        backend: str = DEFAULT_BACKEND,
        search: Optional[SearchConfig] = None,
        seed: Optional[int] = None,
    ):
        base = search or SearchConfig()
        config = SearchConfig(
            depth=depth,
            noise=0.0,
            quiescence_depth=base.quiescence_depth,
            contempt=base.contempt,
        )
        self.searcher = Searcher(genome, config, random.Random(seed))
        self.backend = backend
        self._state: Optional[GameState] = None  # partida até o último lance da Luna

    @property
    def last_score(self) -> Optional[float]:
        """Avaliação do último lance escolhido, em centipeões, do ponto de vista da
        Luna (positivo = Luna melhor). O rating e o bot do Lichess usam para desistir."""
        return self.searcher.last_score

    def new_game(self, color: object = None) -> None:
        self._state = None

    def choose_move(self, fen: str, legal_moves: Sequence[str]) -> str:
        state = self._follow(fen)
        move = self.searcher.choose_move(state)
        uci = state.uci(move) if move is not None else None
        if uci not in legal_moves:
            self._state = None
            return legal_moves[0]
        state.push(move)
        self._state = state
        return uci

    def _follow(self, fen: str) -> GameState:
        """Estado com histórico que chega a ``fen``, ou um novo a partir dela."""
        key = _position_key(fen)
        state = self._state
        if state is not None:
            for move in state.legal_moves():  # o lance do adversário
                state.push(move)
                if _position_key(state.fen()) == key:
                    return state
                state.pop()
            if state.ply:  # a mesma posição de antes, se o nosso lance não valeu
                state.pop()
                if _position_key(state.fen()) == key:
                    return state
        return new_game(self.backend, fen)


def player_from_version(name_or_path: str, depth: int = OFFICIAL_DEPTH) -> LunaPlayer:
    from luna.versions import load_version

    version = load_version(name_or_path)
    return LunaPlayer(version.genome, depth=depth, search=version.search)


def official_factory() -> LunaPlayer:
    """Luna oficial (``luna/versions/oficial.txt``) em profundidade 3, sem ruído.

    ``LUNA_VERSION`` (nome ou caminho de uma versão) e ``LUNA_DEPTH`` sobrepõem."""
    from luna.versions import official_name

    name = os.environ.get("LUNA_VERSION") or official_name()
    return player_from_version(name, int(os.environ.get("LUNA_DEPTH", OFFICIAL_DEPTH)))
