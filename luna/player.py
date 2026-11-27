"""A Luna como jogadora das partidas que contam: rating contra o Stockfish e Lichess.

Uso: ``python -m rating ... --player luna.player:official_factory`` ou
``python -m lichess_bot play --player luna.player:official_factory``.

Duas diferenças em relação ao treino, decididas pelo Lucas com base na análise de
2026-10-08:

- **Profundidade maior** e sem ruído. Até 2026-10-31 era 3 fixo (a mesma Luna
  em profundidade 3 venceu a de profundidade 2 por +319 ± 54 Elo). Desde então é
  a escala ``OFFICIAL_SCHEDULE`` pedida pelo Lucas: 2 meios-lances do lance 1 ao
  9, 4 do 10 ao 16 e 5 do 17 em diante. ``LUNA_DEPTH`` fixa uma profundidade.
- **Orçamento de tempo** (``luna.search.TimeBudget``, pedido do Lucas em
  2026-11-27, no lugar do limite fixo de 14 s de 2026-11-02): teto normal de 20 s
  por lance; até 5 lances por partida podem ir até 40 s, só quando a busca está
  instável; lance óbvio e estável sai antes. ``LUNA_TIME_LIMIT`` muda o teto normal
  (0 desliga tudo), ``LUNA_EXTENDED_TIME`` o teto estendido e ``LUNA_EXTENSIONS`` o
  número de lances estendidos por partida. No Lichess, ``set_clock`` recebe o relógio
  e os tetos encolhem para caber no tempo que resta.
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
from luna.promotion import OFFICIAL_BUDGET, OFFICIAL_MOVE_TIME, official_search
from luna.resign import sees_forced_draw
from luna.search import SearchConfig, Searcher, TimeBudget

#: Primeiro lance fixo da Luna em partidas que começam da posição inicial (pedido do
#: Lucas em 2026-11-27): 1.e4 de brancas e 1...c6 de pretas (Caro-Kann ou, contra
#: 1.d4, eslava). Nos confrontos de rating as partidas saem do livro, depois do lance 1,
#: então isso não muda a medição.
FIRST_MOVES = {"white": "e2e4", "black": "c7c6"}
#: Ruído na raiz do Lichess: cada lance recebe um sorteio uniforme de ±2,5 centipeões, então
#: a Luna sorteia entre lances que diferem até 5 centipeões (pedido do Lucas em 2026-11-27,
#: para não ser previsível). Mates não recebem ruído.
LICHESS_NOISE = 2.5
_START_PLACEMENT = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"


def _first_move(fen: str, first_moves: Optional[dict]) -> Optional[str]:
    """O lance fixo, se esta é a primeira jogada da Luna numa partida da posição inicial."""
    if not first_moves:
        return None
    placement, side, castling, _, _, fullmove = (fen.split() + [""] * 6)[:6]
    if fullmove != "1" or castling != "KQkq":
        return None
    if side == "w" and placement == _START_PLACEMENT:
        return first_moves.get("white")
    if side == "b" and placement.startswith("rnbqkbnr/pppppppp/"):  # pretas ainda intactas
        return first_moves.get("black")
    return None


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
        time_limit: Optional[float] = OFFICIAL_MOVE_TIME,
        budget: Optional[TimeBudget] = None,
        noise: float = 0.0,
        first_moves: Optional[dict] = None,
    ):
        base = search or SearchConfig()
        config = official_search(depth, time_limit, budget)  # None = escala por lance
        config.quiescence_depth = base.quiescence_depth
        config.contempt = base.contempt
        config.noise = noise
        self.first_moves = first_moves
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

    @property
    def last_info(self) -> dict:
        """Tempo, profundidade, nós e se o último lance usou extensão (vazio sem orçamento)."""
        return self.searcher.last_info

    def new_game(self, color: object = None) -> None:
        self._state = None
        self.searcher.new_game()

    def set_clock(self, time_ms: Optional[float], inc_ms: Optional[float] = None) -> None:
        """Relógio do Lichess (milissegundos): os tetos de tempo passam a caber nele."""
        if time_ms is None:
            self.searcher.clock = None
        else:
            self.searcher.clock = (float(time_ms) / 1000.0, float(inc_ms or 0) / 1000.0)

    def choose_move(self, fen: str, legal_moves: Sequence[str]) -> str:
        state = self._follow(fen)
        fixed = _first_move(fen, self.first_moves)
        if fixed in legal_moves:
            state.push(state.parse_uci(fixed))
            self._state = state
            return fixed
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
            # Não continua a partida guardada: é outra partida, com créditos novos.
            clock = self.searcher.clock
            self.searcher.new_game()
            self.searcher.clock = clock
        return new_game(self.backend, fen)


def player_from_version(
    name_or_path: str,
    depth: Optional[int] = None,
    time_limit: Optional[float] = OFFICIAL_MOVE_TIME,
    budget: Optional[TimeBudget] = None,
    noise: float = 0.0,
    first_moves: Optional[dict] = None,
    seed: Optional[int] = None,
) -> LunaPlayer:
    from luna.versions import load_version

    version = load_version(name_or_path)
    return LunaPlayer(
        version.genome,
        depth=depth,
        search=version.search,
        seed=seed,
        time_limit=time_limit,
        budget=budget,
        noise=noise,
        first_moves=first_moves,
    )


def official_factory() -> LunaPlayer:
    """Luna oficial (``luna/versions/oficial.txt``) na escala oficial de profundidade, sem ruído.

    ``LUNA_VERSION`` (nome ou caminho de uma versão), ``LUNA_DEPTH`` e
    ``LUNA_TIME_LIMIT`` (teto normal por lance; 0 desliga), ``LUNA_EXTENDED_TIME``
    (teto dos lances estendidos), ``LUNA_EXTENSIONS`` (lances estendidos por partida),
    ``LUNA_NOISE`` (ruído na raiz, centipeões; padrão 0) e ``LUNA_SEED`` (semente do
    ruído) sobrepõem. Joga 1.e4 e 1...c6 a partir da posição inicial (``FIRST_MOVES``).
    Sem ruído por padrão: é a jogadora dos confrontos de rating."""
    from dataclasses import replace

    from luna.versions import official_name

    env = os.environ.get
    name = env("LUNA_VERSION") or official_name()
    depth = env("LUNA_DEPTH")
    limit = env("LUNA_TIME_LIMIT")
    time_limit = float(limit) if limit else OFFICIAL_MOVE_TIME
    budget = OFFICIAL_BUDGET
    if env("LUNA_EXTENDED_TIME"):
        budget = replace(budget, extended_time=float(env("LUNA_EXTENDED_TIME")))
    if env("LUNA_EXTENSIONS"):
        budget = replace(budget, max_extensions=int(env("LUNA_EXTENSIONS")))
    seed = env("LUNA_SEED")
    return player_from_version(
        name,
        int(depth) if depth else None,
        time_limit,
        budget,
        noise=float(env("LUNA_NOISE") or 0.0),
        first_moves=FIRST_MOVES,
        seed=int(seed) if seed else None,
    )


def lichess_factory() -> LunaPlayer:
    """A Luna do Lichess: a oficial com o ruído ``LICHESS_NOISE`` (lances que diferem até
    5 centipeões são sorteados), para não repetir sempre as mesmas partidas.
    ``LUNA_NOISE`` muda o ruído (0 desliga)."""
    player = official_factory()
    noise = os.environ.get("LUNA_NOISE")
    player.searcher.config.noise = float(noise) if noise else LICHESS_NOISE
    return player
