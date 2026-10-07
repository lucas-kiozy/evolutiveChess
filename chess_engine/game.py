"""Execução de uma partida completa entre dois jogadores.

Um jogador é qualquer função ``jogador(board) -> lance`` que devolva um dos
lances de ``board.legal_moves()``. O tabuleiro recebido é o da partida: o
jogador pode usar ``push``/``pop`` para pensar, desde que deixe a posição como
estava.
"""

from dataclasses import dataclass, field

from .board import Board, Outcome, move_to_uci
from .tables import BLACK, WHITE


@dataclass
class GameResult:
    """Resumo de uma partida, com os números que a Luna usa como aptidão."""

    outcome: Outcome
    moves: list = field(default_factory=list)   # lances em UCI
    start_fen: str = ""
    final_fen: str = ""
    white_moves: int = 0                         # lances feitos pelas brancas
    black_moves: int = 0
    white_checks: int = 0                        # xeques dados pelas brancas
    black_checks: int = 0

    @property
    def winner(self):
        return self.outcome.winner

    @property
    def plies(self):
        return len(self.moves)

    def moves_by(self, color):
        return self.white_moves if color == WHITE else self.black_moves

    def checks_by(self, color):
        return self.white_checks if color == WHITE else self.black_checks


def play_game(white, black, board=None, max_plies=None, claim_draw=True):
    """Joga até o fim e devolve um ``GameResult``.

    ``max_plies`` limita o tamanho da partida; se for atingido, o resultado é
    empate com ``termination == "max_plies"``.
    """
    board = board if board is not None else Board()
    start_fen = board.fen()
    start_ply = board.ply
    players = {WHITE: white, BLACK: black}
    moves = []
    while True:
        outcome = board.outcome(claim_draw)
        if outcome is not None:
            break
        if max_plies is not None and board.ply - start_ply >= max_plies:
            outcome = Outcome(None, "max_plies")
            break
        move = players[board.turn](board)
        if move not in board.legal_moves():
            raise ValueError(f"Jogador devolveu lance ilegal: {move_to_uci(move)} em {board.fen()}")
        moves.append(move_to_uci(move))
        board.push(move)
    return GameResult(
        outcome=outcome,
        moves=moves,
        start_fen=start_fen,
        final_fen=board.fen(),
        white_moves=board.moves_made(WHITE),
        black_moves=board.moves_made(BLACK),
        white_checks=board.checks_given(WHITE),
        black_checks=board.checks_given(BLACK),
    )
