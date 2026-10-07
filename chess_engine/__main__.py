"""Jogo de xadrez no terminal.

    python -m chess_engine                 # dois jogadores no mesmo terminal
    python -m chess_engine --aleatorio     # você de brancas contra lances aleatórios
    python -m chess_engine --aleatorio --pretas
    python -m chess_engine --fen "<FEN>"   # começa de uma posição

Digite lances em SAN (``Nf3``, ``exd5``, ``O-O``, ``e8=Q``) ou UCI (``g1f3``).
Comandos: ``lances``, ``desfazer``, ``fen``, ``sair``.
"""

import argparse
import random
import sys

from .board import STARTING_FEN, Board
from .tables import PIECE_SYMBOLS, WHITE

UNICODE = {
    "K": "♔", "Q": "♕", "R": "♖", "B": "♗", "N": "♘", "P": "♙",
    "k": "♚", "q": "♛", "r": "♜", "b": "♝", "n": "♞", "p": "♟",
}

TERMINATIONS = {
    "checkmate": "xeque-mate",
    "stalemate": "afogamento",
    "insufficient_material": "material insuficiente",
    "seventyfive_moves": "regra dos 75 lances",
    "fivefold_repetition": "quíntupla repetição",
    "fifty_moves": "regra dos 50 lances",
    "threefold_repetition": "tripla repetição",
}


def render(board, flipped=False):
    ranks = range(8) if flipped else range(7, -1, -1)
    files = range(7, -1, -1) if flipped else range(8)
    lines = []
    for rank in ranks:
        row = []
        for file in files:
            p = board.squares[rank * 8 + file]
            if p:
                sym = PIECE_SYMBOLS[abs(p)]
                row.append(UNICODE[sym.upper() if p > 0 else sym])
            else:
                row.append("·")
        lines.append(f"{rank + 1} " + " ".join(row))
    lines.append("  " + " ".join("abcdefgh"[f] for f in files))
    return "\n".join(lines)


def read_move(board):
    while True:
        try:
            text = input(f"{'Brancas' if board.turn == WHITE else 'Pretas'} > ").strip()
        except EOFError:
            return None
        if not text:
            continue
        if text == "sair":
            return None
        if text == "lances":
            print(" ".join(sorted(board.san(m) for m in board.legal_moves())))
            continue
        if text == "fen":
            print(board.fen())
            continue
        if text == "desfazer":
            return "undo"
        for parse in (board.parse_uci, board.parse_san):
            try:
                return parse(text)
            except ValueError:
                pass
        print("Lance inválido. Digite 'lances' para ver as opções.")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m chess_engine", description="Xadrez no terminal")
    parser.add_argument("--fen", default=STARTING_FEN, help="posição inicial")
    parser.add_argument("--aleatorio", action="store_true", help="joga contra lances aleatórios")
    parser.add_argument("--pretas", action="store_true", help="com --aleatorio, você joga de pretas")
    args = parser.parse_args(argv)

    board = Board(args.fen)
    human = -WHITE if args.pretas else WHITE
    while True:
        print()
        print(render(board, flipped=args.aleatorio and human != WHITE))
        outcome = board.outcome()
        if outcome is not None:
            print(f"\nFim de jogo: {outcome.result()} ({TERMINATIONS[outcome.termination]})")
            return 0
        if board.is_check():
            print("Xeque!")
        if args.aleatorio and board.turn != human:
            move = random.choice(board.legal_moves())
            print(f"Computador joga {board.san(move)}")
            board.push(move)
            continue
        move = read_move(board)
        if move is None:
            return 0
        if move == "undo":
            # Contra o computador, desfaz também a resposta dele.
            for _ in range(2 if args.aleatorio else 1):
                if board.ply:
                    board.pop()
            continue
        board.push(move)


if __name__ == "__main__":
    sys.exit(main())
