"""Exportação das partidas da Luna em PGN (Portable Game Notation).

Funciona com qualquer backend: refaz a partida a partir dos lances UCI
guardados no ``GameRecord`` e pede ao backend a notação SAN de cada lance.
"""

from __future__ import annotations

import textwrap
from typing import Iterable, Optional

from luna.adapters import DEFAULT_BACKEND, new_game
from luna.match import GameRecord

_RESULT = {"white": "1-0", "black": "0-1", None: "1/2-1/2"}

_TERMINATION = {
    "checkmate": "normal",
    "resignation": "normal",
    "stalemate": "normal",
    "insufficient_material": "normal",
    "threefold_repetition": "normal",
    "fivefold_repetition": "normal",
    "fifty_moves": "normal",
    "seventyfive_moves": "normal",
    "max_plies": "adjudication",
}


def game_to_pgn(
    record: GameRecord,
    event: str = "Luna",
    round_: str = "?",
    date: str = "????.??.??",
    backend: str = DEFAULT_BACKEND,
    extra_headers: Optional[dict[str, str]] = None,
) -> str:
    result = _RESULT[record.winner]
    headers = {
        "Event": event,
        "Site": "evolutiveChess",
        "Date": date,
        "Round": round_,
        "White": record.white_id,
        "Black": record.black_id,
        "Result": result,
        "PlyCount": str(record.plies),
        "Termination": _TERMINATION.get(record.termination, "normal"),
        "LunaTermination": record.termination,
        "WhiteChecks": str(record.white_checks),
        "BlackChecks": str(record.black_checks),
    }
    if extra_headers:
        headers.update(extra_headers)

    state = new_game(backend)
    tokens: list[str] = []
    for i, text in enumerate(record.moves):
        move = state.parse_uci(text)
        if state.white_to_move:
            tokens.append(f"{i // 2 + 1}.")
        tokens.append(state.san(move))
        state.push(move)
    tokens.append(result)

    tag_lines = "\n".join(f'[{k} "{_escape(v)}"]' for k, v in headers.items())
    movetext = textwrap.fill(" ".join(tokens), width=80)
    return f"{tag_lines}\n\n{movetext}\n"


def games_to_pgn(records: Iterable[GameRecord], **kwargs) -> str:
    """Várias partidas num único texto PGN, separadas por linha em branco."""
    games = []
    for n, record in enumerate(records, start=1):
        games.append(game_to_pgn(record, round_=str(n), **kwargs))
    return "\n".join(games)


def _escape(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"')
