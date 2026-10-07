"""Stockfish com força limitada, usado como adversário de rating conhecido.

Calibração: com ``UCI_LimitStrength=true``, o Stockfish mira a força dada em
``UCI_Elo``. Segundo a documentação oficial do Stockfish (README, opção
``UCI_Elo``), essa escala foi calibrada no controle de tempo 60s+0,6s e
ancorada na lista CCRL 40/4. Por isso o padrão aqui é simular esse relógio.
No Stockfish 16 a faixa aceita vai de 1320 a 3190.

Importante: CCRL não é a escala do Lichess (Glicko-2) nem a da FIDE. O número
obtido aqui é uma estimativa offline para saber *quando* tentar o Lichess; o
rating real só aparece depois de jogar lá.
"""

from __future__ import annotations

import os
import shutil
import time
from dataclasses import dataclass
from typing import Optional, Sequence

import chess
import chess.engine

#: Faixa de UCI_Elo do Stockfish 16 (verificada em tempo de execução).
DEFAULT_MIN_ELO = 1320
DEFAULT_MAX_ELO = 3190


def find_stockfish() -> Optional[str]:
    """Procura o executável em $STOCKFISH_PATH, no PATH ou em /usr/games."""
    env = os.environ.get("STOCKFISH_PATH")
    if env and os.path.exists(env):
        return env
    found = shutil.which("stockfish")
    if found:
        return found
    for candidate in ("/usr/games/stockfish", "/usr/local/bin/stockfish"):
        if os.path.exists(candidate):
            return candidate
    return None


@dataclass(frozen=True)
class TimeControl:
    """Relógio do Stockfish: tempo base e incremento, em segundos."""

    base: float = 60.0
    increment: float = 0.6

    @classmethod
    def parse(cls, text: str) -> "TimeControl":
        """Aceita ``"60+0.6"``."""
        base, _, inc = text.partition("+")
        return cls(float(base), float(inc or 0))


class StockfishOpponent:
    """``MovePlayer`` que joga com força ``elo`` (escala do UCI_Elo)."""

    def __init__(
        self,
        elo: int,
        path: Optional[str] = None,
        time_control: TimeControl = TimeControl(),
        movetime: Optional[float] = None,
        threads: int = 1,
        hash_mb: int = 16,
    ):
        path = path or find_stockfish()
        if not path:
            raise FileNotFoundError(
                "Stockfish não encontrado. Instale (ex.: 'sudo apt install stockfish') "
                "ou defina STOCKFISH_PATH."
            )
        self.engine = chess.engine.SimpleEngine.popen_uci(path)
        opt = self.engine.options.get("UCI_Elo")
        self.min_elo = int(opt.min) if opt and opt.min is not None else DEFAULT_MIN_ELO
        self.max_elo = int(opt.max) if opt and opt.max is not None else DEFAULT_MAX_ELO
        self.elo = max(self.min_elo, min(self.max_elo, int(elo)))
        self.engine.configure(
            {
                "UCI_LimitStrength": True,
                "UCI_Elo": self.elo,
                "Threads": threads,
                "Hash": hash_mb,
            }
        )
        self.time_control = time_control
        self.movetime = movetime
        self._clock = time_control.base
        self._game_id: object = object()

    def new_game(self, color: chess.Color | None = None) -> None:
        self._clock = self.time_control.base
        self._game_id = object()  # faz o python-chess mandar "ucinewgame"

    def _limit(self, board: chess.Board) -> chess.engine.Limit:
        if self.movetime is not None:
            return chess.engine.Limit(time=self.movetime)
        tc = self.time_control
        # O relógio do adversário não importa para a decisão; usamos o mesmo valor.
        return chess.engine.Limit(
            white_clock=max(self._clock, 0.05),
            black_clock=max(self._clock, 0.05),
            white_inc=tc.increment,
            black_inc=tc.increment,
        )

    def choose_move(self, fen: str, legal_moves: Sequence[str]) -> str:
        board = chess.Board(fen)
        start = time.monotonic()
        result = self.engine.play(board, self._limit(board), game=self._game_id)
        elapsed = time.monotonic() - start
        self._clock = self._clock - elapsed + self.time_control.increment
        if result.move is None:  # não deveria acontecer em posição não terminal
            return legal_moves[0]
        return result.move.uci()

    def close(self) -> None:
        try:
            self.engine.quit()
        except chess.engine.EngineTerminatedError:
            pass

    def __enter__(self) -> "StockfishOpponent":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
