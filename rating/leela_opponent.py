"""Leela Chess Zero (lc0) limitada por nós, adversária da régua de rating da Luna.

Com um número fixo de nós e ``SmartPruningFactor=0`` a força da Leela não depende do
relógio nem da máquina, só da rede e dos nós; por isso ela serve de âncora estável
(a Luna, que joga por tempo, é a única parte que varia com a máquina).

A rede usada no projeto é a oficial ID394 (192x15), em CPU (``--backend=blas``).
Caminhos: ``LC0_PATH`` (executável) e ``LEELA_WEIGHTS`` (arquivo da rede).
A Leela usa os planos de histórico da rede, então o jogador guarda o tabuleiro e
descobre o lance do adversário a partir da FEN recebida.
"""

from __future__ import annotations

import os
import shutil
from typing import Optional, Sequence

import chess
import chess.engine

DEFAULT_WEIGHTS = "/mnt/project-files/luna-treinos/lc0/weights_394.pb.gz"


def find_lc0() -> Optional[str]:
    env = os.environ.get("LC0_PATH")
    if env and os.path.exists(env):
        return env
    found = shutil.which("lc0")
    if found:
        return found
    for candidate in ("/home/claude/lc0bin/lc0", "/usr/local/bin/lc0"):
        if os.path.exists(candidate):
            return candidate
    return None


def _same(a: chess.Board, b: chess.Board) -> bool:
    return (
        a.board_fen() == b.board_fen()
        and a.turn == b.turn
        and a.castling_rights == b.castling_rights
        and a.ep_square == b.ep_square
    )


class LeelaOpponent:
    """``MovePlayer`` da Leela com ``nodes`` nós por lance."""

    def __init__(self, nodes: int, path: Optional[str] = None, weights: Optional[str] = None):
        path = path or find_lc0()
        if not path:
            raise FileNotFoundError("lc0 não encontrado; defina LC0_PATH.")
        self.nodes = int(nodes)
        self.engine = chess.engine.SimpleEngine.popen_uci([path, "--backend=blas"])
        weights = weights or os.environ.get("LEELA_WEIGHTS", DEFAULT_WEIGHTS)
        self.engine.configure({"WeightsFile": weights, "Threads": 1, "SmartPruningFactor": 0})
        self.board: Optional[chess.Board] = None
        self._game = object()

    def new_game(self, color: object = None) -> None:
        self.board = None
        self._game = object()

    def choose_move(self, fen: str, legal_moves: Sequence[str]) -> str:
        target = chess.Board(fen)
        if self.board is not None and not _same(self.board, target):
            for move in self.board.legal_moves:
                self.board.push(move)
                if _same(self.board, target):
                    break
                self.board.pop()
            else:
                self.board = None
        if self.board is None:
            self.board = target
        res = self.engine.play(self.board, chess.engine.Limit(nodes=self.nodes), game=self._game)
        move = res.move or chess.Move.from_uci(legal_moves[0])
        self.board.push(move)
        return move.uci()

    def close(self) -> None:
        try:
            self.engine.quit()
        except Exception:  # noqa: BLE001
            pass
