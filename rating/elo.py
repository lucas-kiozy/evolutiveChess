"""Estimativa de rating de desempenho pelo modelo logístico de Elo.

Base teórica
------------
* Elo, A. (1978). *The Rating of Chessplayers, Past and Present*. A pontuação
  esperada contra um adversário de rating ``r_o`` é
  ``E = 1 / (1 + 10 ** ((r_o - r) / 400))``.
* Esse é o modelo de comparação pareada de Bradley & Terry (1952, *Biometrika*
  39:324-345) numa escala logarítmica de base 10; a estimativa de máxima
  verossimilhança (MLE) e o erro-padrão pela informação de Fisher seguem o
  tratamento usual desses modelos (ver Glickman, 1999, *Applied Statistics*
  48:377-394, que deriva o Glicko a partir do mesmo modelo).
* Empates contam 0,5, como no sistema Elo. Uma priori normal fraca
  (regularização) evita estimativas infinitas quando a Luna ganha ou perde
  todas as partidas, ideia análoga à do BayesElo/WHR de Coulom (2008,
  *Computers and Games*, LNCS 5131).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence

#: Fator da escala Elo: ln(10) / 400.
_K = math.log(10) / 400.0


def expected_score(rating: float, opponent_rating: float) -> float:
    """Pontuação esperada (0..1) de ``rating`` contra ``opponent_rating``."""
    return 1.0 / (1.0 + 10.0 ** ((opponent_rating - rating) / 400.0))


@dataclass(frozen=True)
class GameResult:
    """Uma partida contra um adversário de rating conhecido.

    ``score`` é 1 (vitória), 0,5 (empate) ou 0 (derrota), do ponto de vista
    do jogador avaliado.
    """

    opponent_rating: float
    score: float

    def __post_init__(self) -> None:
        if self.score not in (0.0, 0.5, 1.0):
            raise ValueError(f"score precisa ser 0, 0.5 ou 1; recebido {self.score}")


@dataclass(frozen=True)
class RatingEstimate:
    rating: float
    stderr: float
    games: int
    score: float  # pontos somados
    #: True quando nenhuma informação veio dos jogos (ex.: lista vazia).
    from_prior_only: bool = False

    def interval(self, z: float = 1.96) -> tuple[float, float]:
        """Intervalo de confiança normal aproximado (z=1,96 → 95%)."""
        return (self.rating - z * self.stderr, self.rating + z * self.stderr)

    @property
    def score_rate(self) -> float:
        return self.score / self.games if self.games else 0.0


def estimate_rating(
    results: Iterable[GameResult],
    prior_mean: float = 1500.0,
    prior_sd: float = 700.0,
    max_iter: int = 100,
    tol: float = 1e-6,
) -> RatingEstimate:
    """MAP (máxima verossimilhança com priori normal fraca) por Newton-Raphson.

    A log-verossimilhança do modelo logístico é côncava, e a priori normal a
    torna estritamente côncava, então o método de Newton converge para o
    máximo único.
    """
    games: Sequence[GameResult] = list(results)
    total = sum(g.score for g in games)
    if not games:
        return RatingEstimate(prior_mean, prior_sd, 0, 0.0, from_prior_only=True)

    inv_var = 1.0 / (prior_sd**2)
    # Ponto de partida: rating de desempenho clássico (média ± 400·(V−D)/N).
    mean_opp = sum(g.opponent_rating for g in games) / len(games)
    wins_minus_losses = sum(2 * g.score - 1 for g in games)
    r = mean_opp + 400.0 * wins_minus_losses / len(games)

    hessian = -inv_var
    for _ in range(max_iter):
        grad = -(r - prior_mean) * inv_var
        hessian = -inv_var
        for g in games:
            e = expected_score(r, g.opponent_rating)
            grad += _K * (g.score - e)
            hessian -= _K * _K * e * (1.0 - e)
        step = grad / hessian
        r -= step
        if abs(step) < tol:
            break

    stderr = math.sqrt(-1.0 / hessian)
    return RatingEstimate(rating=r, stderr=stderr, games=len(games), score=total)


def games_needed(stderr_target: float, p: float = 0.5) -> int:
    """Quantas partidas, perto de 50% de pontuação, dão o erro-padrão pedido.

    Útil para planejar: ~40 partidas → ~55 Elo de erro-padrão; ~160 → ~27.
    """
    if not 0 < p < 1:
        raise ValueError("p precisa estar entre 0 e 1")
    info_per_game = _K * _K * p * (1 - p)
    return math.ceil(1.0 / (info_per_game * stderr_target**2))
