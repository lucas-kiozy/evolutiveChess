"""Ritmo dos lances da Luna em partidas contra pessoas (pedido do Lucas).

Tempo total de cada lance da Luna, contando o tempo que ela pensa:

* lances 1 a 6: 20 s;
* lances 7 a 40: 1 + X s, com X inteiro aleatório de 0 a 15;
* do lance 41 em diante: Y s, com Y inteiro aleatório de 16 a 90.

"Lance" é o número do lance da própria Luna (1º lance dela, 2º lance dela...).
Treino e medição de rating não usam espera nenhuma.

Proteção do relógio: a espera nunca passa de uma fração do tempo que resta
(``clock_fraction``, padrão 8%) mais 90% do incremento. Assim, num relógio
curto, a Luna joga mais rápido em vez de perder por tempo.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MovePacing:
    opening_moves: int = 6
    opening_seconds: float = 20.0
    middle_until: int = 40
    middle_extra: tuple[int, int] = (0, 15)  # X em 1 + X
    late_range: tuple[int, int] = (16, 90)  # Y
    clock_fraction: float = 0.08
    increment_fraction: float = 0.9
    rng: random.Random = field(default_factory=random.Random)

    def target_seconds(self, move_number: int) -> float:
        """Tempo desejado para o ``move_number``-ésimo lance da Luna (começa em 1)."""
        if move_number < 1:
            raise ValueError("move_number começa em 1")
        if move_number <= self.opening_moves:
            return self.opening_seconds
        if move_number <= self.middle_until:
            return 1 + self.rng.randint(*self.middle_extra)
        return float(self.rng.randint(*self.late_range))

    def clock_budget(self, remaining_ms: Optional[int], increment_ms: Optional[int]) -> float:
        """Teto de segundos para o lance, pelo relógio. Sem relógio, sem teto."""
        if remaining_ms is None:
            return float("inf")
        remaining = max(0.0, remaining_ms / 1000.0)
        inc = max(0.0, (increment_ms or 0) / 1000.0)
        return remaining * self.clock_fraction + inc * self.increment_fraction

    def seconds_for(
        self,
        move_number: int,
        remaining_ms: Optional[int] = None,
        increment_ms: Optional[int] = None,
    ) -> float:
        return min(self.target_seconds(move_number), self.clock_budget(remaining_ms, increment_ms))


class NoPacing:
    """Sem espera (treino, testes de rating)."""

    def seconds_for(self, move_number: int, remaining_ms=None, increment_ms=None) -> float:
        return 0.0
