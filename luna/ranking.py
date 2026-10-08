"""Ordenação das Lunas pela força estimada com o modelo de Bradley–Terry.

Com 18 partidas por Luna, somar a régua 5/2/-1 compara Lunas que enfrentaram
adversárias diferentes e trata igual quem tem 18 partidas e a elite que tem 36 ou
mais. Na análise de 2026-10-08, a melhor de cada geração foi uma filha nova com 18
partidas em 27 de 32 gerações (maldição do vencedor), e o desempate por estilo
decidiu a segunda vaga da elite em 9 de 32. O Lucas decidiu trocar a soma pelo
modelo de força:

- Bradley e Terry (1952, Biometrika 39(3/4):324-345): a chance de A vencer B é
  r_A / (r_A + r_B). Empate conta meio ponto para cada lado, o placar 1/½/0 de que a
  régua 5/2/-1 é uma transformação afim, então a régua continua valendo no cálculo.
- Estimativa pelo algoritmo MM de Hunter (2004, Annals of Statistics 32(1):384-406),
  com todas as partidas da geração, as contra campeãs do hall da fama e as
  acumuladas pela elite. O modelo leva em conta a força de cada adversária.
- Cada Luna recebe ainda ``prior_games`` partidas virtuais (metade vitórias, metade
  derrotas) contra uma adversária fixa de força média. É um encolhimento para a
  média no espírito de Efron e Morris (1975, JASA 70(350):311-319): quem tem poucas
  partidas fica mais perto da média, e a vantagem artificial de quem tem só 18
  partidas some. k partidas virtuais equivalem a uma distribuição a priori com
  desvio de ~347/√k Elo; o padrão 12 dá ~100 Elo, entre a diferença real medida hoje
  entre as Lunas (~15 Elo) e a esperada com os genes novos de busca e de final
  (~100 Elo, seção 4 da análise).

- O bônus da vitória por desistência (régua 6 em vez de 5) entra como uma fração de
  vitória virtual contra a mesma adversária média: ``bonus[p]`` vitórias virtuais
  (ou derrotas, se negativo). Partidas com peso fracionário cabem no algoritmo MM,
  que maximiza a verossimilhança ponderada da mesma forma.

O erro de cada força usa a informação de Fisher de cada Luna, sem as covariâncias.
É uma aproximação, usada só para decidir quando a fronteira da elite precisa de
partidas extras.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Optional

from luna.match import GameRecord

ELO_PER_LN = 400.0 / math.log(10.0)
_SCORE = {"white": 1.0, "black": 0.0, None: 0.5}


@dataclass(frozen=True)
class Strength:
    elo: float  # força relativa à adversária média virtual (0)
    error: float  # erro-padrão aproximado, em Elo
    games: int  # partidas reais


def game_results(records: Iterable[GameRecord]) -> list[tuple[str, str, float]]:
    """(brancas, pretas, placar das brancas) de cada partida."""
    return [(r.white_id, r.black_id, _SCORE[r.winner]) for r in records]


def results_of(player: str, results: Iterable[tuple[str, str, float]]) -> list[list]:
    """[adversária, placar] de cada partida de ``player``, do ponto de vista dela."""
    out = []
    for a, b, s in results:
        if a == player:
            out.append([b, s])
        elif b == player:
            out.append([a, 1.0 - s])
    return out


def bradley_terry(
    results: Iterable[tuple[str, str, float]],
    prior_games: float = 12.0,
    iterations: int = 1000,
    tolerance: float = 1e-10,
    bonus: Optional[dict[str, float]] = None,
) -> dict[str, Strength]:
    """Força de cada jogadora a partir de (a, b, placar de a) com 1/½/0.

    ``bonus``: vitórias virtuais extras de cada jogadora contra a adversária média
    (negativo = derrotas virtuais)."""
    games: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    score: dict[str, float] = defaultdict(float)
    played: dict[str, int] = defaultdict(int)
    for a, b, s in results:
        games[a][b] += 1
        games[b][a] += 1
        score[a] += s
        score[b] += 1.0 - s
        played[a] += 1
        played[b] += 1
    players = sorted(games)
    bonus = bonus or {}
    # Partidas e pontos virtuais de cada jogadora contra a adversária média.
    virtual = {p: prior_games + abs(bonus.get(p, 0.0)) for p in players}
    virtual_score = {p: prior_games / 2.0 + max(bonus.get(p, 0.0), 0.0) for p in players}
    r = {p: 1.0 for p in players}
    for _ in range(iterations):
        change = 0.0
        new = {}
        for p in players:
            # A adversária virtual tem força fixa 1 (Elo 0).
            denom = virtual[p] / (r[p] + 1.0)
            denom += sum(n / (r[p] + r[q]) for q, n in games[p].items())
            new[p] = (score[p] + virtual_score[p]) / denom
            change = max(change, abs(math.log(new[p] / r[p])))
        r = new
        if change < tolerance:
            break
    out = {}
    for p in players:
        info = virtual[p] * r[p] / (r[p] + 1.0) ** 2
        info += sum(n * r[p] * r[q] / (r[p] + r[q]) ** 2 for q, n in games[p].items())
        out[p] = Strength(ELO_PER_LN * math.log(r[p]), ELO_PER_LN / math.sqrt(info), played[p])
    return out
