"""Critério de aptidão definido pelo Lucas.

1. Melhor é a Luna que precisou de menos lances para dar xeque-mate.
2. Em caso de empate no critério 1, vence a Luna que deu menos xeques.

Agregação sobre as várias partidas de uma geração:
- Lunas que deram pelo menos um mate vêm antes das que não deram nenhum;
  entre elas, menor média de lances até o mate é melhor.
- Desempate: menor média de xeques dados por partida.

Modo ``fallback="points"`` (opcional, desligado por padrão): só para as Lunas
que não deram mate, ordena por pontos (vitória 1, empate 0,5) e saldo de
material ao fim da partida antes do desempate por xeques. Não altera em nada a
ordem das Lunas que deram mate.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Iterable

from luna.match import GameRecord

FALLBACKS = ("pure", "points")


@dataclass
class Stats:
    games: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    mates: int = 0
    mate_moves: list[int] = field(default_factory=list)
    checks_given: int = 0
    material: int = 0  # soma do saldo de material do ponto de vista desta Luna

    @property
    def mean_mate_moves(self) -> float | None:
        return sum(self.mate_moves) / len(self.mate_moves) if self.mate_moves else None

    @property
    def checks_per_game(self) -> float:
        return self.checks_given / self.games if self.games else 0.0

    @property
    def points(self) -> float:
        return self.wins + 0.5 * self.draws

    def to_dict(self) -> dict:
        d = asdict(self)
        d["mean_mate_moves"] = self.mean_mate_moves
        d["checks_per_game"] = self.checks_per_game
        d["points"] = self.points
        return d


def collect_stats(records: Iterable[GameRecord]) -> dict[str, Stats]:
    stats: dict[str, Stats] = {}
    for r in records:
        for color, ident in (("white", r.white_id), ("black", r.black_id)):
            s = stats.setdefault(ident, Stats())
            s.games += 1
            s.checks_given += r.white_checks if color == "white" else r.black_checks
            s.material += r.material_balance if color == "white" else -r.material_balance
            if r.winner is None:
                s.draws += 1
            elif r.winner == color:
                s.wins += 1
                if r.mate_moves is not None:
                    s.mates += 1
                    s.mate_moves.append(r.mate_moves)
            else:
                s.losses += 1
    return stats


def sort_key(s: Stats, fallback: str = "pure") -> tuple:
    """Chave de ordenação: menor é melhor."""
    if fallback not in FALLBACKS:
        raise ValueError(f"fallback deve ser um de {FALLBACKS}")
    if s.mates:
        return (0, s.mean_mate_moves, s.checks_per_game, 0.0, 0.0)
    if fallback == "points":
        games = s.games or 1
        return (1, 0.0, -s.points / games, -s.material / games, s.checks_per_game)
    return (1, 0.0, s.checks_per_game, 0.0, 0.0)


def rank(stats: dict[str, Stats], fallback: str = "pure") -> list[str]:
    """IDs do melhor para o pior."""
    return sorted(stats, key=lambda i: (sort_key(stats[i], fallback), i))
