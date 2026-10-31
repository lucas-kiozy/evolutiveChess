"""A Luna como jogadora das partidas que contam: rating contra o Stockfish e Lichess.

Uso: ``python -m rating ... --player luna.player:official_factory`` ou
``python -m lichess_bot play --player luna.player:official_factory``.

Duas diferenças em relação ao treino, decididas pelo Lucas com base na análise de
2026-10-08:

- **Profundidade maior** e sem ruído. Até 2026-10-31 era 3 fixo (a mesma Luna
  em profundidade 3 venceu a de profundidade 2 por +319 ± 54 Elo). Desde então é
  a escala ``OFFICIAL_SCHEDULE`` pedida pelo Lucas: 2 meios-lances do lance 1 ao
  9, 4 do 10 ao 16 e 5 do 17 em diante. ``LUNA_DEPTH`` fixa uma profundidade.
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
from luna.promotion import official_search
from luna.resign import sees_forced_draw
from luna.search import SearchConfig, Searcher


def _position_key(fen: str) -> str:
    """Peças, vez e roques: o que identifica a posição para seguir a partida."""
    return " ".join(fen.split()[:3])


class LunaPlayer:
    """Cumpre ``rating.player.MovePlayer``: ``choose_move(fen, lances_uci) -> uci``."""

    def __init__(
        self,
        genome: Genome,
        depth: Optional[int] = None,
        backend: str = DEFAULT_BACKEND,
        search: Optional[SearchConfig] = None,
        seed: Optional[int] = None,
    ):
        base = search or SearchConfig()
        config = official_search(depth)  # sem ruído; None = escala por lance
        config.quiescence_depth = base.quiescence_depth
        config.contempt = base.contempt
        self.searcher = Searcher(genome, config, random.Random(seed))
        self.backend = backend
        self._state: Optional[GameState] = None  # partida até o último lance da Luna

    @property
    def last_score(self) -> Optional[float]:
        """Avaliação do último lance escolhido, em centipeões, do ponto de vista da
        Luna (positivo = Luna melhor). O rating e o bot do Lichess usam para desistir."""
        return self.searcher.last_score

    def sees_forced_draw(self) -> bool:
        """Na posição do último ``choose_move``, a Luna enxerga empate forçado
        (``luna.resign.sees_forced_draw``)? Se sim, ela não desiste mesmo com a
        avaliação perdida. Sem partida guardada, responde False."""
        state = self._state
        if state is None or not state.ply:
            return False
        move = state.pop()
        try:
            return sees_forced_draw(state)
        finally:
            state.push(move)

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


def player_from_version(name_or_path: str, depth: Optional[int] = None) -> LunaPlayer:
    from luna.versions import load_version

    version = load_version(name_or_path)
    return LunaPlayer(version.genome, depth=depth, search=version.search)


def official_factory() -> LunaPlayer:
    """Luna oficial (``luna/versions/oficial.txt``) na escala oficial de profundidade, sem ruído.

    ``LUNA_VERSION`` (nome ou caminho de uma versão) e ``LUNA_DEPTH`` sobrepõem."""
    from luna.versions import official_name

    name = os.environ.get("LUNA_VERSION") or official_name()
    depth = os.environ.get("LUNA_DEPTH")
    return player_from_version(name, int(depth) if depth else None)
