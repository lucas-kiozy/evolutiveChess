"""Estimador adaptativo do rating da Luna contra Stockfish calibrado.

Como funciona
-------------
1. Joga lotes de partidas contra o Stockfish com ``UCI_Elo`` fixo, alternando
   as cores. Cada lote roda em paralelo (um processo por partida, cada um com
   o seu Stockfish e a sua instância do jogador).
2. Depois de cada lote, recalcula o rating por máxima verossimilhança
   (``rating.elo.estimate_rating``).
3. O próximo lote é jogado com o Stockfish perto da estimativa atual: é onde a
   partida traz mais informação (a informação de Fisher por partida,
   ``p·(1−p)``, é máxima quando a chance de vitória é 50%).
4. Para quando atinge o número máximo de partidas ou o erro-padrão desejado.

"Pronta para o Lichess" significa: o limite inferior do intervalo de confiança
(padrão 90%, z=1,645) já está acima do alvo (padrão 1600). Isso evita
declarar a meta batida por sorte em poucas partidas.

Limitação conhecida: o Stockfish 16 não joga abaixo de UCI_Elo 1320. Se a Luna
perde quase tudo contra 1320, o relatório diz apenas que ela está abaixo
dessa âncora, sem inventar um número.
"""

from __future__ import annotations

import json
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Optional

import chess

from rating.elo import GameResult, RatingEstimate, estimate_rating
from rating.match import DEFAULT_MAX_PLIES, play_game
from rating.player import PlayerFactory
from rating.resign import ResignPolicy
from rating.stockfish_opponent import (
    DEFAULT_MAX_ELO,
    DEFAULT_MIN_ELO,
    StockfishOpponent,
    TimeControl,
)


@dataclass
class EstimatorConfig:
    target: float = 1600.0
    max_games: int = 60
    batch_size: int = 4  # partidas por lote = processos em paralelo
    stderr_target: float = 40.0
    z: float = 1.645  # 90% bilateral → limite inferior com 95% unilateral
    start_elo: int = DEFAULT_MIN_ELO
    elo_step: int = 50  # arredonda o nível do adversário
    min_elo: int = DEFAULT_MIN_ELO
    max_elo: int = DEFAULT_MAX_ELO
    time_control: TimeControl = field(default_factory=TimeControl)
    movetime: Optional[float] = None  # se definido, ignora o relógio
    max_plies: int = DEFAULT_MAX_PLIES
    stockfish_path: Optional[str] = None
    history_file: Optional[Path] = None  # JSONL com cada partida
    #: A Luna desiste pela regra de rating.resign (desligado para manter as
    #: medições comparáveis com as anteriores; o Stockfish nunca desiste).
    luna_resigns: bool = False


@dataclass
class GameLog:
    opponent_elo: int
    luna_color: str  # "white" | "black"
    score: float
    result: str
    termination: str
    plies: int
    seconds: float
    pgn: str


@dataclass
class RatingReport:
    estimate: RatingEstimate
    target: float
    z: float
    games: list[GameLog]

    @property
    def low(self) -> float:
        return self.estimate.interval(self.z)[0]

    @property
    def high(self) -> float:
        return self.estimate.interval(self.z)[1]

    @property
    def ready_for_lichess(self) -> bool:
        return self.estimate.games > 0 and self.low >= self.target

    @property
    def below_anchor_floor(self) -> bool:
        """Verdadeiro se a Luna pontuou pouco até contra o Stockfish mais fraco."""
        floor = [g for g in self.games if g.opponent_elo <= min(x.opponent_elo for x in self.games)]
        if len(floor) < 4:
            return False
        rate = sum(g.score for g in floor) / len(floor)
        return rate <= 0.1

    def summary(self) -> str:
        e = self.estimate
        if not e.games:
            return "Nenhuma partida jogada."
        lines = [
            f"Partidas: {e.games} | pontos: {e.score:g} ({100 * e.score_rate:.0f}%)",
        ]
        if self.below_anchor_floor:
            floor = min(g.opponent_elo for g in self.games)
            lines.append(
                f"Rating estimado: abaixo de ~{floor} (a âncora mais fraca do Stockfish); "
                "ainda longe do alvo."
            )
        else:
            lines.append(
                f"Rating estimado: {e.rating:.0f} ± {e.stderr:.0f} "
                f"(IC {self.z:.3g}σ: {self.low:.0f} a {self.high:.0f}), escala CCRL/UCI_Elo"
            )
        lines.append(
            f"Alvo {self.target:.0f}: "
            + (
                "atingido, pronta para o Lichess."
                if self.ready_for_lichess
                else "ainda não atingido."
            )
        )
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "rating": self.estimate.rating,
            "stderr": self.estimate.stderr,
            "games": self.estimate.games,
            "score": self.estimate.score,
            "low": self.low,
            "high": self.high,
            "target": self.target,
            "ready_for_lichess": self.ready_for_lichess,
            "below_anchor_floor": self.below_anchor_floor,
        }


def _play_one(args: tuple) -> GameLog:
    """Executa uma partida (roda dentro de um processo filho)."""
    factory, elo, luna_white, cfg = args
    luna = factory()
    start = time.monotonic()
    with StockfishOpponent(
        elo,
        path=cfg.stockfish_path,
        time_control=cfg.time_control,
        movetime=cfg.movetime,
    ) as sf:
        white, black = (luna, sf) if luna_white else (sf, luna)
        headers = {
            "Event": "Luna rating estimate",
            "White": "Luna" if luna_white else f"Stockfish UCI_Elo {sf.elo}",
            "Black": f"Stockfish UCI_Elo {sf.elo}" if luna_white else "Luna",
        }
        luna_side = chess.WHITE if luna_white else chess.BLACK
        resign = {luna_side: ResignPolicy()} if cfg.luna_resigns else None
        res = play_game(white, black, max_plies=cfg.max_plies, headers=headers, resign=resign)
        actual_elo = sf.elo
    color = chess.WHITE if luna_white else chess.BLACK
    return GameLog(
        opponent_elo=actual_elo,
        luna_color="white" if luna_white else "black",
        score=res.score_for(color),
        result=res.result,
        termination=res.termination,
        plies=res.plies,
        seconds=time.monotonic() - start,
        pgn=res.pgn,
    )


def _round_elo(value: float, cfg: EstimatorConfig) -> int:
    stepped = int(round(value / cfg.elo_step) * cfg.elo_step)
    return max(cfg.min_elo, min(cfg.max_elo, stepped))


class RatingEstimator:
    def __init__(
        self,
        player_factory: PlayerFactory,
        config: EstimatorConfig | None = None,
        progress: Callable[[RatingReport], None] | None = None,
        runner: Callable[[list[tuple]], list[GameLog]] | None = None,
    ):
        """``runner`` permite trocar a execução em paralelo (ex.: em testes)."""
        self.factory = player_factory
        self.cfg = config or EstimatorConfig()
        self.progress = progress
        self._runner = runner or self._run_parallel

    def _run_parallel(self, jobs: list[tuple]) -> list[GameLog]:
        if len(jobs) == 1:
            return [_play_one(jobs[0])]
        with ProcessPoolExecutor(max_workers=len(jobs)) as pool:
            return list(pool.map(_play_one, jobs))

    def _report(self, logs: list[GameLog]) -> RatingReport:
        est = estimate_rating(GameResult(float(g.opponent_elo), g.score) for g in logs)
        return RatingReport(est, self.cfg.target, self.cfg.z, logs)

    def run(self) -> RatingReport:
        cfg = self.cfg
        logs: list[GameLog] = []
        next_elo = _round_elo(cfg.start_elo, cfg)
        report = self._report(logs)
        while len(logs) < cfg.max_games:
            n = min(cfg.batch_size, cfg.max_games - len(logs))
            jobs = [(self.factory, next_elo, (len(logs) + i) % 2 == 0, cfg) for i in range(n)]
            batch = self._runner(jobs)
            logs.extend(batch)
            self._append_history(batch)
            report = self._report(logs)
            if self.progress:
                self.progress(report)
            if report.estimate.stderr <= cfg.stderr_target:
                break
            next_elo = _round_elo(report.estimate.rating, cfg)
        return report

    def _append_history(self, batch: list[GameLog]) -> None:
        if not self.cfg.history_file:
            return
        path = Path(self.cfg.history_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            for g in batch:
                fh.write(json.dumps(asdict(g), ensure_ascii=False) + "\n")
