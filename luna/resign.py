"""Quando a Luna desiste: a regra única do treino, do rating, do Lichess e do tabuleiro.

Regra (decisão do Lucas em 2026-10-08):

1. A avaliação da busca, do ponto de vista da Luna, fica em ``RESIGN_SCORE``
   (-1000 centipeões, dez peões) ou menos, ou é mate contra ela, por
   ``RESIGN_MOVES`` (3) lances seguidos dela. São os padrões do lichess-bot.
   Exigir lances seguidos evita desistir no meio de uma troca.
2. **E** ela não enxerga nenhuma possibilidade de empate forçado. Só é checado
   quando a regra 1 já mandaria desistir, e qualquer um destes basta para ela
   continuar jogando:
   - o adversário não tem material para dar mate (só o rei, ou rei e uma peça
     menor, sem peões, torres nem damas);
   - uma busca E-OU de até ``DRAW_SEARCH_PLIES`` (8) meios-lances acha um
     caminho que ela impõe até o empate: afogamento, material insuficiente,
     tripla repetição ou regra dos 50 lances. Nos lances dela, os primeiros
     ``DRAW_FULL_PLIES`` (4) meios-lances olham todos os lances; depois, só os
     que dão xeque ou empatam (ou dão mate) na hora. Nas respostas do
     adversário, todas precisam levar ao empate. Oito meios-lances bastam para
     um xeque perpétuo simples repetir a posição três vezes;
   - se a busca passar de ``DRAW_SEARCH_NODES`` (20.000) nós sem conclusão, na
     dúvida ela não desiste.

A regra junta a versão do treino (busca completa curta, material de mate) com a
do bot do Lichess (busca longa só com xeques, limite de nós), que foi feita no
``rating/resign.py``. Ela usa a interface ``GameState``, então funciona com
qualquer backend; ``state_from_moves`` monta o estado com o histórico a partir dos
lances UCI da partida, para quem só tem a lista de lances.

A avaliação da regra 1 já considera os empates que a busca principal enxerga,
porque ela pontua empate como ``-contempt`` (no máximo -150), bem acima de -1000.
"""

from __future__ import annotations

from typing import Optional, Sequence

from luna.adapters import DEFAULT_BACKEND, new_game
from luna.game_interface import GameState

RESIGN_SCORE = -1000.0  # centipeões
RESIGN_MOVES = 3
DRAW_SEARCH_PLIES = 8
DRAW_FULL_PLIES = 4
DRAW_SEARCH_NODES = 20_000


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


class _OutOfNodes(Exception):
    pass


def _is_draw(state: GameState) -> bool:
    outcome = state.outcome(claim_draw=True)
    return outcome is not None and outcome.winner is None


def can_force_draw(
    state: GameState,
    plies: int = DRAW_SEARCH_PLIES,
    full_plies: int = DRAW_FULL_PLIES,
    max_nodes: int = DRAW_SEARCH_NODES,
) -> bool:
    """Quem vai jogar consegue forçar empate (ou mate) em até ``plies`` meios-lances?

    Sem conclusão em ``max_nodes`` nós, devolve True (na dúvida, não desiste)."""
    nodes = 0

    def tick() -> None:
        nonlocal nodes
        nodes += 1
        if nodes > max_nodes:
            raise _OutOfNodes

    def ours(left: int, ply: int) -> bool:
        if left <= 0:
            return False
        for move in state.legal_moves():
            tick()
            check = state.gives_check(move)
            if not check and ply >= full_plies and left > 1:
                # Depois da parte completa, lance quieto só serve se empatar na hora.
                state.push(move)
                ok = _is_draw(state) or state.is_checkmate()
                state.pop()
            else:
                state.push(move)
                ok = _is_draw(state) or state.is_checkmate() or theirs(left - 1, ply + 1)
                state.pop()
            if ok:
                return True
        return False

    def theirs(left: int, ply: int) -> bool:
        if left <= 0:
            return False
        for move in state.legal_moves():
            tick()
            state.push(move)
            ok = _is_draw(state) or (not state.is_checkmate() and ours(left - 1, ply + 1))
            state.pop()
            if not ok:
                return False
        return True

    start = state.ply
    try:
        return ours(plies, 0)
    except _OutOfNodes:
        while state.ply > start:  # desfaz os lances que a busca deixou no meio
            state.pop()
        return True


def sees_forced_draw(state: GameState, plies: int = DRAW_SEARCH_PLIES) -> bool:
    """Quem vai jogar enxerga empate forçado? Se sim, não desiste. ``state`` precisa
    ter o histórico da partida para a tripla repetição contar."""
    return _is_draw(state) or opponent_cannot_mate(state) or can_force_draw(state, plies)


def state_from_moves(
    moves: Sequence[str], start_fen: Optional[str] = None, backend: str = DEFAULT_BACKEND
) -> GameState:
    """Estado com histórico depois dos lances UCI ``moves`` a partir de ``start_fen``."""
    state = new_game(backend, start_fen)
    for uci in moves:
        state.push(state.parse_uci(uci))
    return state


def board_sees_forced_draw(board: object, plies: int = DRAW_SEARCH_PLIES) -> bool:
    """``sees_forced_draw`` para um ``chess.Board`` do python-chess (rating e Lichess),
    refazendo a partida a partir de ``board.root()`` com ``board.move_stack``."""
    moves = [m.uci() for m in board.move_stack]
    state = state_from_moves(moves, board.root().fen(), "python-chess")
    return sees_forced_draw(state, plies)


def should_resign(tracker: ResignTracker, score_cp: float, state: GameState) -> bool:
    """Chame depois de escolher o lance e antes de jogá-lo, com ``state`` na posição
    em que a jogadora vai jogar (e com o histórico da partida, para as repetições)."""
    return tracker.update(score_cp) and not sees_forced_draw(state)
