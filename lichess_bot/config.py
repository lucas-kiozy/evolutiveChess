"""Configuração do bot. O token só é lido do ambiente (LICHESS_BOT_TOKEN)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

TOKEN_ENV = "LICHESS_BOT_TOKEN"


@dataclass
class BotConfig:
    #: Aceita partidas valendo rating (precisa delas para o rating subir).
    accept_rated: bool = True
    accept_casual: bool = True
    #: Relógio mínimo: base + 60 × incremento, em segundos. Com o ritmo de
    #: lances pedido pelo Lucas (lichess_bot/pacing.py), uma partida média de 60
    #: lances da Luna gasta ~1470 s (6×20 + 34×8,5 + 20×53), então 1500 s cobrem
    #: o ritmo inteiro numa partida típica. Ex.: 25+0, 15+10 e 30+20 passam;
    #: 10+5 não. Em partidas longas, a proteção do relógio acelera os lances.
    min_clock_budget: int = 1500
    #: Tempo base máximo (padrão 3 h) e incremento máximo, em segundos.
    max_initial: int = 10800
    max_increment: int = 60
    #: Ritmos aceitos. Bullet e blitz não cabem no ritmo de lances; correspondência
    #: fica de fora porque o bot joga uma partida por vez e ela duraria dias.
    speeds: tuple[str, ...] = ("rapid", "classical")
    #: Ritmo de lances contra pessoas (20 s, 1+X, 16 a 90 s). False = sem espera.
    pacing: bool = True
    #: Desistência (rating/resign.py): avaliação ≤ resign_score cp por
    #: resign_moves lances seguidos da Luna, como no lichess-bot.
    resign_score: int = -1000
    resign_moves: int = 3
    #: Pasta onde as partidas jogadas ficam guardadas para o aprendizado.
    data_dir: Path = field(default_factory=lambda: Path("lichess_bot/runs"))
    #: Matchmaking: desafiar outros bots quando ficar ocioso (desligado por padrão).
    matchmaking: bool = False
    matchmaking_idle_seconds: float = 120.0
    matchmaking_clock: tuple[int, int] = (1800, 20)  # 30+20, cabe no ritmo de lances
    matchmaking_rating_window: int = 300


def read_token() -> str:
    token = os.environ.get(TOKEN_ENV, "").strip()
    if not token:
        raise SystemExit(
            f"Defina a variável de ambiente {TOKEN_ENV} com o token da conta BOT "
            "(permissão 'bot:play'). Veja lichess_bot/GUIA.md."
        )
    return token
