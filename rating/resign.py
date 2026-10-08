"""Critério de desistência da Luna, igual no rating, no Lichess e no tabuleiro.

Regra (o padrão do lichess-bot: ``resign_score: -1000``, ``resign_moves: 3``):
a Luna desiste quando a avaliação da raiz da busca, do ponto de vista dela, fica
em -1000 centipeões ou menos (ou é mate contra ela) por 3 lances seguidos dela.
Exigir lances seguidos evita desistir no meio de uma troca.

Decisão do Lucas: a Luna **só desiste se não enxergar nenhuma possibilidade de
empate forçado**. A busca de empate forçado é a regra única do projeto,
``luna.resign.board_sees_forced_draw`` (afogamento, material insuficiente,
repetição tripla com o histórico real, 50 lances, xeque perpétuo em até 8
meios-lances, adversário sem material de mate; na dúvida, não desiste). Este
módulo só a aplica a qualquer ``MovePlayer`` e ao ``chess.Board`` do bot.

De onde vem a avaliação:

1. ``player.should_resign(fen)``, se o jogador decidir sozinho;
2. ``player.last_score``: escore em centipeões do último ``choose_move``, do
   ponto de vista de quem escolheu o lance;
3. sem nenhum dos dois, o material (P=1, N=3, B=3, R=5, Q=9) × 100 depois do
   lance escolhido, como aproximação: 10 pontos atrás ≈ -1000 cp.

No placar, uma desistência vale como qualquer vitória: 1 ponto para quem não
desistiu, 0 para quem desistiu, como no Lichess.
"""

from __future__ import annotations

from typing import Optional

import chess

# Regra única do projeto, mantida pela frente da Luna em luna/resign.py.
from luna.resign import RESIGN_MOVES, RESIGN_SCORE, board_sees_forced_draw

PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
}


def material_balance(board: chess.Board, color: chess.Color) -> int:
    """Material de ``color`` menos o do adversário, em pontos."""
    total = 0
    for piece_type, value in PIECE_VALUES.items():
        total += value * len(board.pieces(piece_type, color))
        total -= value * len(board.pieces(piece_type, not color))
    return total


class ResignPolicy:
    """Conta lances seguidos com avaliação ≤ ``score`` e diz quando desistir."""

    def __init__(self, score: float = RESIGN_SCORE, moves: int = RESIGN_MOVES):
        if score >= 0 or moves <= 0:
            raise ValueError("score precisa ser negativo e moves positivo")
        self.score = score
        self.moves = moves
        self._streak = 0

    def new_game(self) -> None:
        self._streak = 0

    def update(self, score_cp: float) -> bool:
        """Registra a avaliação de um lance da Luna; True = desistir agora."""
        self._streak = self._streak + 1 if score_cp <= self.score else 0
        return self._streak >= self.moves


def score_after(player: object, fen: str, move_uci: str) -> float:
    """Avaliação (cp) do lance escolhido, do ponto de vista de quem o escolheu."""
    score = getattr(player, "last_score", None)
    if isinstance(score, (int, float)):
        return float(score)
    board = chess.Board(fen)
    side = board.turn
    board.push_uci(move_uci)
    return 100.0 * material_balance(board, side)


def wants_to_resign(
    player: object, policy: Optional[ResignPolicy], board: chess.Board, move_uci: str
) -> bool:
    """Chame depois de ``choose_move`` e antes de jogar o lance escolhido.

    ``board`` é a posição antes do lance, com o histórico da partida.
    """
    own = getattr(player, "should_resign", None)
    if callable(own):
        return bool(own(board.fen()))
    if policy is None:
        return False
    if not policy.update(score_after(player, board.fen(), move_uci)):
        return False
    return not board_sees_forced_draw(board)
