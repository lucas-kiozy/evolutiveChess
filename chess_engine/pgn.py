"""Exportação de partidas em PGN (Portable Game Notation)."""

import datetime

from .board import STARTING_FEN, Board

_ROSTER = ("Event", "Site", "Date", "Round", "White", "Black", "Result")


def to_pgn(moves, start_fen=STARTING_FEN, result="*", headers=None):
    """Monta o texto PGN de uma partida.

    ``moves`` é uma lista de lances em UCI (como ``GameResult.moves``) ou de
    lances inteiros. ``headers`` acrescenta ou substitui etiquetas, por exemplo
    ``{"White": "Luna g12 #3", "Black": "Luna g12 #7"}``.
    """
    tags = {
        "Event": "?",
        "Site": "?",
        "Date": datetime.date.today().strftime("%Y.%m.%d"),
        "Round": "?",
        "White": "?",
        "Black": "?",
        "Result": result,
    }
    if start_fen != STARTING_FEN:
        tags["SetUp"] = "1"
        tags["FEN"] = start_fen
    if headers:
        tags.update(headers)

    board = Board(start_fen)
    tokens = []
    for i, move in enumerate(moves):
        if isinstance(move, str):
            move = board.parse_uci(move)
        if board.turn == 1:
            tokens.append(f"{board.fullmove_number}.")
        elif i == 0:
            tokens.append(f"{board.fullmove_number}...")
        tokens.append(board.san(move))
        board.push(move)
    tokens.append(tags["Result"])

    lines, line = [], ""
    for token in tokens:
        if line and len(line) + 1 + len(token) > 79:
            lines.append(line)
            line = token
        else:
            line = f"{line} {token}" if line else token
    lines.append(line)

    ordered = [k for k in _ROSTER] + [k for k in tags if k not in _ROSTER]
    header_text = "\n".join(f'[{k} "{_escape(str(tags[k]))}"]' for k in ordered)
    return f"{header_text}\n\n" + "\n".join(lines) + "\n"


def _escape(value):
    return value.replace("\\", "\\\\").replace('"', '\\"')
