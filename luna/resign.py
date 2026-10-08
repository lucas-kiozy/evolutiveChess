"""Quando a Luna desiste, igual no treino, no rating, no Lichess e no tabuleiro.

Regra (decisão do Lucas em 2026-10-08):

1. A avaliação da busca, do ponto de vista da Luna, fica em ``RESIGN_SCORE``
   (-1000 centipeões, dez peões) ou menos, ou é mate contra ela, por
   ``RESIGN_MOVES`` (3) lances seguidos dela. São os padrões do lichess-bot.
   Exigir lances seguidos evita desistir no meio de uma troca.
2. **E** ela não enxerga nenhuma possibilidade de empate forçado. São duas
   verificações, feitas só quando a regra 1 já mandaria desistir:
   - o adversário não tem material para dar mate (só o rei, ou rei e uma peça
     menor, sem peões, torres nem damas);
   - uma busca E-OU de ``DRAW_SEARCH_PLIES`` meios-lances acha um lance da Luna
     que, contra qualquer resposta, chega a empate: afogamento, material
     insuficiente, regra dos 50 lances, tripla repetição ou repetição de uma
     posição já vista (o mesmo sinal que a busca principal usa para o xeque
     perpétuo). Quatro meios-lances bastam para o xeque perpétuo mais curto.

A avaliação da regra 1 já leva em conta os empates que a busca principal
enxerga, porque ela pontua empate como ``-contempt`` (no máximo -150), bem acima
de -1000. A busca E-OU cobre o que a principal não vê: a regra dos 50 lances, o
material insuficiente e as repetições perdidas pelo corte alfa-beta.
"""

from __future__ import annotations

from luna.game_interface import GameState

RESIGN_SCORE = -1000.0  # centipeões
RESIGN_MOVES = 3
DRAW_SEARCH_PLIES = 4


class ResignTracker:
    """Conta os lances seguidos de uma jogadora com avaliação perdida."""

    def __init__(self, score: float = RESIGN_SCORE, moves: int = RESIGN_MOVES):
        if score >= 0 or moves <= 0:
            raise ValueError("score precisa ser negativo e moves positivo")
        self.score = score
        self.moves = moves
        self.streak = 0

    def update(self, score_cp: float) -> bool:
        """Registra a avaliação de um lance; True = a regra 1 manda desistir."""
        self.streak = self.streak + 1 if score_cp <= self.score else 0
        return self.streak >= self.moves


def opponent_cannot_mate(state: GameState) -> bool:
    """O adversário de quem vai jogar tem só o rei, ou rei e uma peça menor?"""
    side = state.white_to_move
    minors = 0
    for _, piece, white in state.pieces():
        if white == side or piece == "K":
            continue
        if piece in "PRQ":
            return False
        minors += 1
    return minors <= 1


def _is_draw(state: GameState) -> bool:
    if state.is_repetition():
        return True
    outcome = state.outcome(claim_draw=True)
    return outcome is not None and outcome.winner is None


def can_force_draw(state: GameState, plies: int = DRAW_SEARCH_PLIES) -> bool:
    """Quem vai jogar consegue forçar empate (ou mate) em até ``plies`` meios-lances?"""
    if plies <= 0:
        return False
    for move in state.legal_moves():
        state.push(move)
        ok = _is_draw(state) or _all_replies_draw(state, plies - 1)
        state.pop()
        if ok:
            return True
    return False


def _all_replies_draw(state: GameState, plies: int) -> bool:
    replies = state.legal_moves()
    if not replies:  # sem lances e sem empate: o adversário levou mate
        return True
    if plies <= 0:
        return False
    for move in replies:
        state.push(move)
        ok = _is_draw(state) or can_force_draw(state, plies - 1)
        state.pop()
        if not ok:
            return False
    return True


def sees_forced_draw(state: GameState, plies: int = DRAW_SEARCH_PLIES) -> bool:
    """Quem vai jogar enxerga empate forçado? Se sim, não desiste."""
    return opponent_cannot_mate(state) or can_force_draw(state, plies)


def should_resign(tracker: ResignTracker, score_cp: float, state: GameState) -> bool:
    """Chame depois de escolher o lance e antes de jogá-lo, com ``state`` na posição
    em que a jogadora vai jogar (e com o histórico da partida, para as repetições)."""
    return tracker.update(score_cp) and not sees_forced_draw(state)
