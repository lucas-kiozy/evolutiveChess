"""Busca alfa-beta (negamax) com quiescência sobre capturas.

A busca é fixa; só a avaliação evolui. Mates são pontuados como
``MATE_SCORE - ply``, então entre dois mates a busca prefere o mais curto,
o que está alinhado com o critério de aptidão (mate em menos lances).
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
    quiescence_depth: int = 4  # 0 desliga a quiescência
    noise: float = 0.0  # ruído uniforme (centipeões) na raiz, para variar partidas
    # "Contempt": quanto um empate (repetição ou afogamento) vale de menos para quem
    # está buscando. Em autojogo os dois lados querem dar mate, então os dois evitam
    # repetir posições em vez de ficar indo e voltando até a tripla repetição.
    contempt: float = 50.0


class Searcher:
    def __init__(self, genome: Genome, config: SearchConfig, rng: Optional[random.Random] = None):
        self.genome = genome
        self.config = config
        self.rng = rng or random.Random()
        self.nodes = 0

    def choose_move(self, state: GameState) -> Optional[Move]:
        # Ordem UCI antes da ordenação por capturas: desempates e ruído ficam iguais
        # em qualquer backend, independente da ordem em que ele gera os lances.
        moves = self._ordered(state, sorted(state.legal_moves(), key=state.uci))
        if not moves:
            return None
        noise = self.config.noise
        best_move, best_score = moves[0], -INF
        for move in moves:
            # Um lance só pode superar o melhor (já com ruído) se o valor real passar de
            # best_score - noise. Abaixo desse piso o alfa-beta devolve só um limite
            # superior, e nem o maior ruído possível o faria vencer. O ruído entra
            # apenas na comparação, nunca em alpha, e não se aplica a mates.
            alpha = best_score - noise
            state.push(move)
            score = -self._negamax(state, self.config.depth - 1, -INF, -alpha, 1)
            state.pop()
            if score <= alpha:
                continue
            if noise and abs(score) < MATE_SCORE - MAX_PLY:
                score += self.rng.uniform(-noise, noise)
            if score > best_score:
                best_move, best_score = move, score
        return best_move

    def _negamax(self, state: GameState, depth: int, alpha: float, beta: float, ply: int) -> float:
        self.nodes += 1
        if state.is_repetition():
            return self._draw_score(ply)
        moves = state.legal_moves()
        if not moves:
            return -(MATE_SCORE - ply) if state.is_check() else self._draw_score(ply)
        if depth <= 0:
            return self._quiescence(state, alpha, beta, ply, self.config.quiescence_depth)
        for move in self._ordered(state, moves):
            state.push(move)
            score = -self._negamax(state, depth - 1, -beta, -alpha, ply + 1)
            state.pop()
            if score >= beta:
                return score
            if score > alpha:
                alpha = score
        return alpha

    def _draw_score(self, ply: int) -> float:
        """Empate visto do lado a jogar no nó: ruim para a raiz, bom para o adversário."""
        return -self.config.contempt if ply % 2 == 0 else self.config.contempt

    def _quiescence(self, state: GameState, alpha: float, beta: float, ply: int, qdepth: int) -> float:
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
