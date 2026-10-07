"""Critério de aptidão definido pelo Lucas.

Régua por partida: vitória +5, empate +2, derrota -1. A régua é somada nas
partidas e decide primeiro, então uma vitória sempre vale mais que um empate e um
empate mais que uma derrota. A comparação usa a média por partida, que dá a mesma
ordem que a soma quando todas jogam o mesmo número de partidas e continua justa
para a elite, que acumula as partidas das gerações anteriores.

Desempates, nesta ordem, entre Lunas com a mesma média na régua:
1. Pontos de captura nos empates e derrotas, por partida (maior é melhor): peão 0,1;
   cavalo 0,3; bispo 0,4; torre 0,6; dama 2.
2. Menos xeques dados nas partidas vencidas (vencer sendo objetivo no ataque).
3. Menos lances até o mate nas partidas vencidas.

Os pontos de captura ficam como desempate, e não somados à régua, porque somados
um empate com muitas capturas (2 + até 5,4) passaria de uma vitória (5).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Iterable

from luna.match import GameRecord

RESULT_POINTS = {"win": 5.0, "draw": 2.0, "loss": -1.0}
CAPTURE_POINTS = {"P": 0.1, "N": 0.3, "B": 0.4, "R": 0.6, "Q": 2.0}


def capture_score(captures: dict[str, int]) -> float:
    return sum(CAPTURE_POINTS.get(piece, 0.0) * n for piece, n in captures.items())


@dataclass
class Stats:
    games: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    mates: int = 0
    mate_moves: list[int] = field(default_factory=list)
    win_checks: list[int] = field(default_factory=list)  # xeques dados em cada vitória
    checks_given: int = 0
    capture_points: float = 0.0  # soma dos pontos de captura em empates e derrotas

    @property
    def result_points(self) -> float:
        return (
            RESULT_POINTS["win"] * self.wins
            + RESULT_POINTS["draw"] * self.draws
            + RESULT_POINTS["loss"] * self.losses
        )

    @property
    def mean_mate_moves(self) -> float | None:
        return sum(self.mate_moves) / len(self.mate_moves) if self.mate_moves else None

    @property
    def mean_win_checks(self) -> float | None:
        return sum(self.win_checks) / len(self.win_checks) if self.win_checks else None

    @property
    def checks_per_game(self) -> float:
        return self.checks_given / self.games if self.games else 0.0

    def merge(self, other: "Stats") -> None:
        """Soma os resultados de ``other`` (partidas de gerações anteriores)."""
        self.games += other.games
        self.wins += other.wins
        self.draws += other.draws
        self.losses += other.losses
        self.mates += other.mates
        self.mate_moves += other.mate_moves
        self.win_checks += other.win_checks
        self.checks_given += other.checks_given
        self.capture_points += other.capture_points

    @classmethod
    def from_dict(cls, d: dict) -> "Stats":
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in names})

    def to_dict(self) -> dict:
        d = asdict(self)
        d["result_points"] = self.result_points
        d["mean_mate_moves"] = self.mean_mate_moves
        d["mean_win_checks"] = self.mean_win_checks
        d["checks_per_game"] = self.checks_per_game
        return d


def collect_stats(records: Iterable[GameRecord]) -> dict[str, Stats]:
    stats: dict[str, Stats] = {}
    for r in records:
        for color, ident in (("white", r.white_id), ("black", r.black_id)):
            s = stats.setdefault(ident, Stats())
            s.games += 1
            checks = r.white_checks if color == "white" else r.black_checks
            s.checks_given += checks
            captures = r.white_captures if color == "white" else r.black_captures
            if r.winner == color:
                s.wins += 1
                s.win_checks.append(checks)
                if r.mate_moves is not None:
                    s.mates += 1
                    s.mate_moves.append(r.mate_moves)
            elif r.winner is None:
                s.draws += 1
                s.capture_points += capture_score(captures)
            else:
                s.losses += 1
                s.capture_points += capture_score(captures)
    return stats


def sort_key(s: Stats) -> tuple:
    """Chave de ordenação: menor é melhor."""
    inf = float("inf")
    games = s.games or 1
    return (
        -round(s.result_points / games, 9),
        -round(s.capture_points / games, 9),
        s.mean_win_checks if s.win_checks else inf,
        s.mean_mate_moves if s.mate_moves else inf,
    )


def rank(stats: dict[str, Stats]) -> list[str]:
    """IDs do melhor para o pior."""
    return sorted(stats, key=lambda i: (sort_key(stats[i]), i))
