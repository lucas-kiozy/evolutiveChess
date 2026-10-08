"""Busca alfa-beta (negamax) com quiescência sobre capturas.

Mates são pontuados como ``MATE_SCORE - ply``, então entre dois mates a busca
prefere o mais curto, o que está alinhado com o critério de aptidão (mate em menos
lances).

A profundidade e o ruído vêm de ``SearchConfig``. A profundidade da quiescência, o
contempt e as extensões em xeque são genes (``luna.genome``) e evoluem junto com a
avaliação; ``SearchConfig`` só os sobrepõe quando recebe um valor explícito.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional

from luna.evaluation import MATE_SCORE, evaluate
from luna.game_interface import GameState, Move
from luna.genome import Genome

_ORDER_VALUE = {"P": 1, "N": 3, "B": 3, "R": 5, "Q": 9, "K": 0}
INF = float("inf")
MAX_PLY = 1000  # escores acima de MATE_SCORE - MAX_PLY são mates


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
    # ``depth``. None desliga. No treino o padrão é 3 nos lances 5 a 12, pedido do
    # Lucas para ganhar força no meio-jogo sem pagar a profundidade 3 inteira.
    deep_depth: Optional[int] = None
    deep_from_move: int = 5
    deep_to_move: int = 12

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
        )
        return cls(**{k: d[k] for k in keys if k in d})

    def depth_at(self, ply: int) -> int:
        """Profundidade para o meio-lance ``ply`` (0 = primeiro lance das brancas)."""
        move = ply // 2 + 1
        if self.deep_depth and self.deep_from_move <= move <= self.deep_to_move:
            return self.deep_depth
        return self.depth


class Searcher:
    def __init__(self, genome: Genome, config: SearchConfig, rng: Optional[random.Random] = None):
        self.genome = genome
        self.config = config
        self.rng = rng or random.Random()
        self.nodes = 0
        g = genome.genes
        q = config.quiescence_depth
        self.quiescence_depth = int(g["quiescence_depth"] if q is None else q)
        self.contempt = g["contempt"] if config.contempt is None else config.contempt
        self.check_extensions = int(g["check_extension"])

    def choose_move(self, state: GameState) -> Optional[Move]:
        # Ordem UCI antes da ordenação por capturas: desempates e ruído ficam iguais
        # em qualquer backend, independente da ordem em que ele gera os lances.
        moves = self._ordered(state, sorted(state.legal_moves(), key=state.uci))
        if not moves:
            return None
        noise = self.config.noise
        depth = self.config.depth_at(state.ply)
        best_move, best_score = moves[0], -INF
        for move in moves:
            # Um lance só pode superar o melhor (já com ruído) se o valor real passar de
            # best_score - noise. Abaixo desse piso o alfa-beta devolve só um limite
            # superior, e nem o maior ruído possível o faria vencer. O ruído entra
            # apenas na comparação, nunca em alpha, e não se aplica a mates.
            alpha = best_score - noise
            state.push(move)
            score = -self._negamax(state, depth - 1, -INF, -alpha, 1, self.check_extensions)
            state.pop()
            if score <= alpha:
                continue
            if noise and abs(score) < MATE_SCORE - MAX_PLY:
                score += self.rng.uniform(-noise, noise)
            if score > best_score:
                best_move, best_score = move, score
        return best_move

    def _negamax(
        self, state: GameState, depth: int, alpha: float, beta: float, ply: int, extensions: int
    ) -> float:
        self.nodes += 1
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
            self.nodes += 1
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
