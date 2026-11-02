"""Busca alfa-beta (negamax) com quiescência sobre capturas.

Mates são pontuados como ``MATE_SCORE - ply``, então entre dois mates a busca
prefere o mais curto, o que está alinhado com o critério de aptidão (mate em menos
lances).

A profundidade e o ruído vêm de ``SearchConfig``. A profundidade da quiescência, o
contempt e as extensões em xeque são genes (``luna.genome``) e evoluem junto com a
avaliação; ``SearchConfig`` só os sobrepõe quando recebe um valor explícito.

Limite de tempo (``SearchConfig.time_limit``, pedido do Lucas em 2026-11-02): a
busca passa a ser por aprofundamento iterativo, profundidade 1, 2, ... até a pedida,
com o melhor lance da camada anterior buscado primeiro. Quando o tempo acaba, ela
joga o melhor lance da última camada completa, ou o da camada interrompida se ele
já superou aquele (o primeiro lance buscado nela é justamente o anterior). As
camadas rasas custam pouco perto da última (Korf 1985, *Artificial Intelligence*
27:97-109) e melhoram a ordem dos lances da seguinte (Slate & Atkin 1977, Chess 4.5).
Sem ``time_limit`` a busca vai direto à profundidade pedida, como antes.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Optional

from luna.evaluation import MATE_SCORE, evaluate
from luna.game_interface import GameState, Move
from luna.genome import Genome

_ORDER_VALUE = {"P": 1, "N": 3, "B": 3, "R": 5, "Q": 9, "K": 0}
INF = float("inf")
MAX_PLY = 1000  # escores acima de MATE_SCORE - MAX_PLY são mates
#: Segundos por lance em todas as partidas da Luna, treino e oficiais (decisão do
#: Lucas em 2026-11-02).
MOVE_TIME_LIMIT = 14.0
_CLOCK_EVERY = 256  # nós entre consultas ao relógio


class _Timeout(Exception):
    pass


@dataclass
class SearchConfig:
    depth: int = 2
    noise: float = 0.0  # ruído uniforme (centipeões) na raiz, para variar partidas
    # None = usa o gene do genoma. Um número sobrepõe o gene (testes, experimentos).
    quiescence_depth: Optional[int] = None  # 0 desliga a quiescência
    # "Contempt": quanto um empate (repetição ou afogamento) vale de menos para quem
    # está buscando. Em autojogo os dois lados querem dar mate, então os dois evitam
    # repetir posições em vez de ficar indo e voltando até a tripla repetição.
    contempt: Optional[float] = None
    # Janela mais funda: do lance ``deep_from_move`` ao ``deep_to_move`` (contados como
    # no xadrez, um lance = brancas e pretas) a busca usa ``deep_depth`` em vez de
    # ``depth``. None desliga. No treino o padrão é 3 nos lances 8 a 12, pedido do
    # Lucas para ganhar força no meio-jogo sem pagar a profundidade 3 inteira.
    deep_depth: Optional[int] = None
    deep_from_move: int = 8
    deep_to_move: int = 12
    # Escala por lance: ((a partir do lance, profundidade), ...) em ordem crescente.
    # Se existir, manda sobre ``depth`` e a janela funda. Nas partidas oficiais é
    # ``luna.promotion.OFFICIAL_SCHEDULE``.
    schedule: Optional[tuple[tuple[int, int], ...]] = None
    # Segundos por lance. None = sem limite (a busca vai direto à profundidade).
    time_limit: Optional[float] = None

    @classmethod
    def from_dict(cls, d: dict) -> "SearchConfig":
        keys = (
            "depth",
            "noise",
            "quiescence_depth",
            "contempt",
            "deep_depth",
            "deep_from_move",
            "deep_to_move",
            "schedule",
            "time_limit",
        )
        kwargs = {k: d[k] for k in keys if k in d}
        if kwargs.get("schedule") is not None:
            kwargs["schedule"] = tuple((int(m), int(dp)) for m, dp in kwargs["schedule"])
        return cls(**kwargs)

    def depth_at(self, ply: int) -> int:
        """Profundidade para o meio-lance ``ply`` (0 = primeiro lance das brancas)."""
        return self.depth_for_move(ply // 2 + 1)

    def depth_for_move(self, move: int) -> int:
        """Profundidade para o lance ``move`` (contado como no xadrez, a partir de 1)."""
        if self.schedule:
            depth = self.schedule[0][1]
            for start, d in self.schedule:
                if move >= start:
                    depth = d
            return depth
        if self.deep_depth and self.deep_from_move <= move <= self.deep_to_move:
            return self.deep_depth
        return self.depth


def _move_number(state: GameState) -> int:
    """Número do lance da posição, do campo da FEN: vale também para partidas que
    começam de uma FEN, em que alguns backends contam ``ply`` a partir de 0."""
    try:
        return max(1, int(state.fen().split()[5]))
    except (IndexError, ValueError):
        return state.ply // 2 + 1


class Searcher:
    def __init__(self, genome: Genome, config: SearchConfig, rng: Optional[random.Random] = None):
        self.genome = genome
        self.config = config
        self.rng = rng or random.Random()
        self.nodes = 0
        # Escore real (sem o ruído) do lance escolhido na última busca, em centipeões e
        # do ponto de vista de quem jogou; mates valem perto de ±MATE_SCORE.
        self.last_score: Optional[float] = None
        g = genome.genes
        q = config.quiescence_depth
        self.quiescence_depth = int(g["quiescence_depth"] if q is None else q)
        self.contempt = g["contempt"] if config.contempt is None else config.contempt
        self.check_extensions = int(g["check_extension"])
        self._deadline: Optional[float] = None

    def choose_move(self, state: GameState) -> Optional[Move]:
        # Ordem UCI antes da ordenação por capturas: desempates e ruído ficam iguais
        # em qualquer backend, independente da ordem em que ele gera os lances.
        moves = self._ordered(state, sorted(state.legal_moves(), key=state.uci))
        if not moves:
            return None
        depth = self.config.depth_for_move(_move_number(state))
        limit = self.config.time_limit
        if not limit:
            best_move, self.last_score, _ = self._root(state, moves, depth)
            return best_move
        deadline = time.monotonic() + limit
        best_move, best_real = moves[0], 0.0
        start = state.ply
        try:
            for d in range(1, depth + 1):
                # A camada 1 sempre termina (custa milissegundos): garante um lance e
                # um escore para a regra de desistência.
                self._deadline = deadline if d > 1 else None
                best_move, best_real, _ = self._root(state, moves, d)
                moves = [best_move] + [m for m in moves if m != best_move]
                if abs(best_real) >= MATE_SCORE - MAX_PLY:
                    break  # mate achado: mais fundo não muda o lance
        except _Timeout as stop:
            while state.ply > start:  # desfaz os lances que a busca deixou no meio
                state.pop()
            partial = stop.args[0] if stop.args else None
            if partial is not None:  # a camada interrompida já achou algo
                best_move, best_real = partial
        finally:
            self._deadline = None
        self.last_score = best_real
        return best_move

    def _root(self, state: GameState, moves: list[Move], depth: int) -> tuple[Move, float, float]:
        """Busca na raiz até ``depth``; devolve (lance, escore real, escore com ruído).

        Com tempo esgotado levanta ``_Timeout`` com o melhor (lance, escore real)
        entre os lances já buscados por completo nesta camada, ou None."""
        noise = self.config.noise
        best_move, best_score, best_real = moves[0], -INF, -INF
        for move in moves:
            # Um lance só pode superar o melhor (já com ruído) se o valor real passar de
            # best_score - noise. Abaixo desse piso o alfa-beta devolve só um limite
            # superior, e nem o maior ruído possível o faria vencer. O ruído entra
            # apenas na comparação, nunca em alpha, e não se aplica a mates.
            alpha = best_score - noise
            state.push(move)
            try:
                score = -self._negamax(state, depth - 1, -INF, -alpha, 1, self.check_extensions)
            except _Timeout:
                found = (best_move, best_real) if best_score > -INF else None
                raise _Timeout(found) from None
            state.pop()
            if score <= alpha:
                continue
            real = score
            if noise and abs(score) < MATE_SCORE - MAX_PLY:
                score += self.rng.uniform(-noise, noise)
            if score > best_score:
                best_move, best_score, best_real = move, score, real
        return best_move, best_real, best_score

    def _tick(self) -> None:
        self.nodes += 1
        if (
            self._deadline is not None
            and self.nodes % _CLOCK_EVERY == 0
            and time.monotonic() > self._deadline
        ):
            raise _Timeout

    def _negamax(
        self, state: GameState, depth: int, alpha: float, beta: float, ply: int, extensions: int
    ) -> float:
        self._tick()
        if state.is_repetition():
            return self._draw_score(ply)
        moves = state.legal_moves()
        if not moves:
            return -(MATE_SCORE - ply) if state.is_check() else self._draw_score(ply)
        # Extensão em xeque: o lado em xeque tem poucas respostas, então olhar um
        # meio-lance a mais custa pouco e evita julgar a posição no meio de um ataque.
        # ``extensions`` limita quantas vezes isso acontece numa mesma linha.
        if extensions and state.is_check():
            depth += 1
            extensions -= 1
        if depth <= 0:
            return self._quiescence(state, alpha, beta, ply, self.quiescence_depth)
        for move in self._ordered(state, moves):
            state.push(move)
            score = -self._negamax(state, depth - 1, -beta, -alpha, ply + 1, extensions)
            state.pop()
            if score >= beta:
                return score
            if score > alpha:
                alpha = score
        return alpha

    def _draw_score(self, ply: int) -> float:
        """Empate visto do lado a jogar no nó: ruim para a raiz, bom para o adversário."""
        return -self.contempt if ply % 2 == 0 else self.contempt

    def _quiescence(
        self, state: GameState, alpha: float, beta: float, ply: int, qdepth: int
    ) -> float:
        stand_pat = evaluate(state, self.genome)
        if qdepth <= 0 or stand_pat >= beta:
            return stand_pat
        if stand_pat > alpha:
            alpha = stand_pat
        captures = [m for m in state.legal_moves() if state.is_capture(m) or state.is_promotion(m)]
        for move in self._ordered(state, captures):
            self._tick()
            state.push(move)
            score = -self._quiescence(state, -beta, -alpha, ply + 1, qdepth - 1)
            state.pop()
            if score >= beta:
                return score
            if score > alpha:
                alpha = score
        return alpha

    @staticmethod
    def _ordered(state: GameState, moves: list[Move]) -> list[Move]:
        """Capturas primeiro, por MVV-LVA (vítima mais valiosa, agressor menos valioso)."""

        def key(move: Move) -> int:
            victim = state.captured_piece(move)
            score = 0
            if victim:
                score = 10 * _ORDER_VALUE[victim] - _ORDER_VALUE[state.moving_piece(move)] + 100
            if state.is_promotion(move):
                score += 90
            return -score

        return sorted(moves, key=key)
