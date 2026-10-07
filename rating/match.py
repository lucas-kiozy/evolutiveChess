"""Partida entre dois ``MovePlayer`` arbitrada pelo python-chess.

O python-chess é usado só como árbitro neutro (regras, fim de jogo, PGN), para
que a medição de rating não dependa do motor que a Luna usa internamente.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Optional

import chess
import chess.pgn

from rating.player import MovePlayer

#: Limite de lances (meios-lances) antes de declarar empate por adjudicação.
DEFAULT_MAX_PLIES = 500


@dataclass
class MatchResult:
    """Resultado de uma partida do ponto de vista das brancas e das pretas."""

    result: str  # "1-0", "0-1" ou "1/2-1/2"
    termination: str  # checkmate, stalemate, illegal_move, max_plies...
    plies: int
    moves: list[str] = field(default_factory=list)
    checks_by_white: int = 0
    checks_by_black: int = 0
    pgn: str = ""

    def score_for(self, color: chess.Color) -> float:
        if self.result == "1/2-1/2":
            return 0.5
        white_won = self.result == "1-0"
        return 1.0 if white_won == (color == chess.WHITE) else 0.0


def _notify_new_game(player: MovePlayer, color: chess.Color) -> None:
    hook = getattr(player, "new_game", None)
    if callable(hook):
        hook(color)


def play_game(
    white: MovePlayer,
    black: MovePlayer,
    max_plies: int = DEFAULT_MAX_PLIES,
    start_fen: Optional[str] = None,
    headers: Optional[dict[str, str]] = None,
) -> MatchResult:
    """Joga uma partida completa e devolve o resultado.

    Lance ilegal (ou exceção do jogador) conta como derrota de quem errou, para
    que um bug no jogador nunca infle o rating.
    """
    board = chess.Board(start_fen) if start_fen else chess.Board()
    _notify_new_game(white, chess.WHITE)
    _notify_new_game(black, chess.BLACK)
    checks = {chess.WHITE: 0, chess.BLACK: 0}
    result: Optional[str] = None
    termination = ""

    while True:
        outcome = board.outcome(claim_draw=True)
        if outcome is not None:
            result = outcome.result()
            termination = outcome.termination.name.lower()
            break
        if board.ply() >= max_plies:
            result, termination = "1/2-1/2", "max_plies"
            break

        mover = board.turn
        player = white if mover == chess.WHITE else black
        legal = [m.uci() for m in board.legal_moves]
        try:
            uci = player.choose_move(board.fen(), legal)
            move = chess.Move.from_uci(uci)
            if move not in board.legal_moves:
                raise ValueError(f"lance ilegal {uci}")
        except Exception:  # noqa: BLE001 - qualquer falha do jogador = derrota
            result = "0-1" if mover == chess.WHITE else "1-0"
            termination = "illegal_move"
            break
        board.push(move)
        if board.is_check():
            checks[mover] += 1

    game = chess.pgn.Game.from_board(board)
    for key, value in (headers or {}).items():
        game.headers[key] = value
    game.headers["Result"] = result
    game.headers["Termination"] = termination
    buf = io.StringIO()
    print(game, file=buf, end="\n")

    return MatchResult(
        result=result,
        termination=termination,
        plies=board.ply(),
        moves=[m.uci() for m in board.move_stack],
        checks_by_white=checks[chess.WHITE],
        checks_by_black=checks[chess.BLACK],
        pgn=buf.getvalue(),
    )
