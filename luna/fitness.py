"""Critério de aptidão definido pelo Lucas.

Vitórias (toda vitória é por xeque-mate):
1. Melhor é a Luna que precisou de menos lances para dar xeque-mate.
2. Em caso de empate no critério 1, vence a Luna que deu menos xeques.

Empates e derrotas (``fallback="captures"``, o padrão):
- cada peça capturada soma pontos: peão 0,1; cavalo 0,3; bispo 0,4;
  torre 0,6; dama 2;
- cada derrota soma -5.

Agregação sobre as várias partidas de uma geração:
- Lunas que deram pelo menos um mate vêm antes das demais e são ordenadas pela
  menor média de lances até o mate, com desempate pela menor média de xeques
  dados nas partidas que terminaram com o mate dela.
- As demais são ordenadas pela maior média de pontos nas partidas sem vitória,
  com o mesmo desempate por xeques.

``fallback="pure"`` ignora a pontuação de empates e derrotas: entre as Lunas
sem mate só conta a média de xeques.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Iterable

from luna.match import GameRecord

FALLBACKS = ("captures", "pure")

CAPTURE_POINTS = {"P": 0.1, "N": 0.3, "B": 0.4, "R": 0.6, "Q": 2.0}
LOSS_POINTS = -5.0


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
    mate_checks: list[int] = field(default_factory=list)  # xeques dados em cada partida vencida
    checks_given: int = 0
    non_win_points: float = 0.0  # soma da pontuação de empates e derrotas

    @property
    def mean_mate_moves(self) -> float | None:
        return sum(self.mate_moves) / len(self.mate_moves) if self.mate_moves else None

    @property
    def mean_mate_checks(self) -> float | None:
        return sum(self.mate_checks) / len(self.mate_checks) if self.mate_checks else None

    @property
    def checks_per_game(self) -> float:
        return self.checks_given / self.games if self.games else 0.0

    @property
    def mean_non_win_points(self) -> float:
        n = self.draws + self.losses
        return self.non_win_points / n if n else 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["mean_mate_moves"] = self.mean_mate_moves
        d["mean_mate_checks"] = self.mean_mate_checks
        d["checks_per_game"] = self.checks_per_game
        d["mean_non_win_points"] = self.mean_non_win_points
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
                if r.mate_moves is not None:
                    s.mates += 1
                    s.mate_moves.append(r.mate_moves)
                    s.mate_checks.append(checks)
            elif r.winner is None:
                s.draws += 1
                s.non_win_points += capture_score(captures)
            else:
                s.losses += 1
                s.non_win_points += capture_score(captures) + LOSS_POINTS
    return stats


def sort_key(s: Stats, fallback: str = "captures") -> tuple:
    """Chave de ordenação: menor é melhor."""
    if fallback not in FALLBACKS:
        raise ValueError(f"fallback deve ser um de {FALLBACKS}")
    if s.mates:
        return (0, s.mean_mate_moves, s.mean_mate_checks)
    if fallback == "captures":
        return (1, -s.mean_non_win_points, s.checks_per_game)
    return (1, 0.0, s.checks_per_game)


def rank(stats: dict[str, Stats], fallback: str = "captures") -> list[str]:
    """IDs do melhor para o pior."""
    return sorted(stats, key=lambda i: (sort_key(stats[i], fallback), i))
