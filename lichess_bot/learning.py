"""Registro das partidas do Lichess e gancho de aprendizado para a Luna.

A frente da Luna decide *como* aprender; este módulo só garante que cada
partida terminada vire um ``GameRecord`` completo e chegue a quem aprende.
O registro já traz as métricas do critério de aptidão pedido pelo Lucas:
quantos lances a Luna precisou para dar mate e quantos xeques ela deu.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional, Protocol, Sequence, runtime_checkable

import chess
import chess.pgn


@dataclass
class GameRecord:
    game_id: str
    luna_color: str  # "white" | "black"
    moves: list[str]  # UCI
    status: str  # mate, resign, outoftime, draw, stalemate...
    winner: Optional[str]  # "white" | "black" | None
    initial_fen: str = chess.STARTING_FEN
    rated: bool = False
    speed: str = ""
    opponent: str = ""
    opponent_rating: Optional[int] = None
    luna_rating: Optional[int] = None
    luna_rating_diff: Optional[int] = None
    luna_moves: int = 0  # lances completos feitos pela Luna
    checks_by_luna: int = 0
    checks_by_opponent: int = 0
    pgn: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def luna_score(self) -> float:
        if self.winner is None:
            return 0.5
        return 1.0 if self.winner == self.luna_color else 0.0

    @property
    def luna_won_by_mate(self) -> bool:
        return self.status == "mate" and self.winner == self.luna_color


def build_record(
    game_id: str,
    luna_color: str,
    moves: Sequence[str],
    status: str,
    winner: Optional[str],
    initial_fen: str = chess.STARTING_FEN,
    **meta,
) -> GameRecord:
    """Reconstrói a partida para calcular xeques, lances e PGN."""
    board = chess.Board(initial_fen)
    luna = chess.WHITE if luna_color == "white" else chess.BLACK
    checks = {chess.WHITE: 0, chess.BLACK: 0}
    luna_moves = 0
    for uci in moves:
        mover = board.turn
        board.push_uci(uci)
        if mover == luna:
            luna_moves += 1
        if board.is_check():
            checks[mover] += 1
    game = chess.pgn.Game.from_board(board)
    game.headers["Event"] = "Lichess"
    game.headers["Site"] = f"https://lichess.org/{game_id}"
    names = {luna: "Luna", not luna: meta.get("opponent") or "?"}
    game.headers["White"] = names[chess.WHITE]
    game.headers["Black"] = names[chess.BLACK]
    game.headers["Result"] = {"white": "1-0", "black": "0-1"}.get(winner or "", "1/2-1/2")
    return GameRecord(
        game_id=game_id,
        luna_color=luna_color,
        moves=list(moves),
        status=status,
        winner=winner,
        initial_fen=initial_fen,
        luna_moves=luna_moves,
        checks_by_luna=checks[luna],
        checks_by_opponent=checks[not luna],
        pgn=str(game),
        **meta,
    )


@runtime_checkable
class Learner(Protocol):
    """Quem aprende com as partidas (implementado pela frente da Luna)."""

    def on_game_finished(self, record: GameRecord) -> None: ...


class JsonlRecorder:
    """Aprendiz padrão: só guarda as partidas em ``games.jsonl`` e ``games.pgn``."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)

    def on_game_finished(self, record: GameRecord) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        with (self.data_dir / "games.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
        with (self.data_dir / "games.pgn").open("a", encoding="utf-8") as fh:
            fh.write(record.pgn + "\n\n")


def load_records(data_dir: Path) -> list[GameRecord]:
    path = Path(data_dir) / "games.jsonl"
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return [GameRecord(**json.loads(line)) for line in fh if line.strip()]


class LearnerChain:
    """Encadeia vários aprendizes (ex.: gravar em disco e depois a Luna)."""

    def __init__(self, *learners: Learner):
        self.learners = learners

    def on_game_finished(self, record: GameRecord) -> None:
        for learner in self.learners:
            learner.on_game_finished(record)
