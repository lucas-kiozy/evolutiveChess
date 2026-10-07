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
    #: Faixa de tempo base aceita, em segundos (padrão: 3 a 30 minutos).
    min_initial: int = 180
    max_initial: int = 1800
    max_increment: int = 30
    #: Ritmos aceitos pelo Lichess para bots. Correspondência fica de fora
    #: porque o bot joga uma partida por vez e ela poderia durar dias.
    speeds: tuple[str, ...] = ("bullet", "blitz", "rapid", "classical")
    #: Pasta onde as partidas jogadas ficam guardadas para o aprendizado.
    data_dir: Path = field(default_factory=lambda: Path("lichess_bot/runs"))
    #: Matchmaking: desafiar outros bots quando ficar ocioso (desligado por padrão).
    matchmaking: bool = False
    matchmaking_idle_seconds: float = 120.0
    matchmaking_clock: tuple[int, int] = (300, 3)  # 5+3
    matchmaking_rating_window: int = 300


def read_token() -> str:
    token = os.environ.get(TOKEN_ENV, "").strip()
    if not token:
        raise SystemExit(
            f"Defina a variável de ambiente {TOKEN_ENV} com o token da conta BOT "
            "(permissão 'bot:play'). Veja lichess_bot/GUIA.md."
        )
    return token
