"""Valida lances numa posição usando o motor do projeto (chess_engine).

Uso (da raiz do repositório)::

    python .claude/skills/validar-regras-xadrez/scripts/validar.py --fen "<FEN>" --lances "e1g1"
    python .claude/skills/validar-regras-xadrez/scripts/validar.py --lances "e4 e5 Nf3 Nc6 Bb5" --listar
    python .claude/skills/validar-regras-xadrez/scripts/validar.py --fen "<FEN>" --listar --cruzar --json

Os lances podem ser UCI (e2e4, e7e8q) ou SAN (Nf3, O-O, exd6, e8=Q). Eles são
aplicados em sequência; o primeiro lance ilegal interrompe e é explicado.
``--cruzar`` confere lances legais, xeque e resultado com o python-chess, se
estiver instalado.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from chess_engine import (  # noqa: E402
    KING, PAWN, SQUARE_NAMES, STARTING_FEN, WHITE, Board, move_from, move_promotion, move_to,
    move_to_uci, square_index,
)

UCI_RE = re.compile(r"^[a-h][1-8][a-h][1-8][qrbn]?$")
PIECE_NAMES = {1: "peão", 2: "cavalo", 3: "bispo", 4: "torre", 5: "dama", 6: "rei"}
TERMINATIONS = {
    "checkmate": "xeque-mate",
    "stalemate": "afogamento",
    "insufficient_material": "material insuficiente",
    "seventyfive_moves": "regra dos 75 lances",
    "fivefold_repetition": "repetição quíntupla",
    "fifty_moves": "regra dos 50 lances (reivindicável)",
    "threefold_repetition": "repetição tripla (reivindicável)",
}


def color_name(color: int) -> str:
    return "brancas" if color == WHITE else "pretas"


def describe_move(board: Board, move: int) -> dict:
    """Classifica um lance legal antes de aplicá-lo."""
    frm, to, promo = move_from(move), move_to(move), move_promotion(move)
    piece = abs(board.piece_at(frm))
    en_passant = piece == PAWN and to == board.ep_square and board.piece_at(to) == 0
    return {
        "uci": move_to_uci(move),
        "san": board.san(move),
        "peca": PIECE_NAMES[piece],
        "captura": board.is_capture(move),
        "en_passant": en_passant,
        "roque": ("pequeno" if to > frm else "grande") if board.is_castling(move) else None,
        "promocao": PIECE_NAMES[promo] if promo else None,
        "da_xeque": board.gives_check(move),
    }


def explain_castling(board: Board, frm: int, to: int) -> str:
    color = board.turn
    rights = board.fen().split()[2]
    short = to > frm
    flag = ("K" if short else "Q") if color == WHITE else ("k" if short else "q")
    side = "pequeno" if short else "grande"
    if flag not in rights:
        return f"sem direito de roque {side} ({rights!r} na FEN): rei ou torre já se moveram"
    rook = frm + 3 if short else frm - 4
    between = range(min(frm, rook) + 1, max(frm, rook))
    blocked = [SQUARE_NAMES[s] for s in between if board.piece_at(s)]
    if blocked:
        return f"roque {side} bloqueado: há peça(s) em {', '.join(blocked)}"
    if board.is_check():
        return "não pode rocar estando em xeque"
    step = 1 if short else -1
    for sq in (frm + step, frm + 2 * step):
        if board.is_attacked(sq, -color):
            return f"o rei passaria ou pararia em casa atacada ({SQUARE_NAMES[sq]})"
    return "roque ilegal nesta posição"


def explain_illegal(board: Board, text: str) -> str:
    """Motivo provável de um lance ilegal, em português."""
    if not UCI_RE.match(text.lower()):
        uci = san_to_uci_guess(board, text)
        if uci is None:
            return (f"{text!r} não corresponde a nenhum lance legal em SAN; confira a peça, a casa "
                    "e a desambiguação (ex.: Nbd2)")
        text = uci
    text = text.lower()
    frm, to = square_index(text[:2]), square_index(text[2:4])
    piece = board.piece_at(frm)
    if piece == 0:
        return f"não há peça em {text[:2]}"
    if piece * board.turn < 0:
        return f"a peça em {text[:2]} é das {color_name(-board.turn)}, mas é a vez das {color_name(board.turn)}"
    target = board.piece_at(to)
    if target and target * board.turn > 0:
        return f"{text[2:4]} já tem uma peça das {color_name(board.turn)}"
    kind = abs(piece)
    if kind == KING and abs(to - frm) == 2 and frm // 8 == to // 8:
        return explain_castling(board, frm, to)
    last_rank = 7 if board.turn == WHITE else 0
    if kind == PAWN and to // 8 == last_rank and len(text) == 4:
        return "peão chegando à última fileira precisa indicar a promoção (ex.: e7e8q)"
    if len(text) == 5 and not (kind == PAWN and to // 8 == last_rank):
        return "só peão chegando à última fileira pode ter peça de promoção"
    if kind == PAWN and frm % 8 != to % 8 and target == 0 and to != board.ep_square:
        return (f"o peão só anda na diagonal capturando, e {text[2:4]} está vazia; en passant só vale "
                "no lance imediatamente seguinte ao avanço duplo do peão adversário")
    pseudo = pseudo_legal(board, text)
    if pseudo is True:
        return "deixaria o próprio rei em xeque (peça cravada ou xeque não resolvido)"
    if pseudo is False:
        return f"o {PIECE_NAMES[kind]} não pode ir de {text[:2]} para {text[2:4]} nesta posição"
    if board.is_check():
        return "o rei está em xeque e esse lance não resolve o xeque (ou a peça não anda assim)"
    return f"o {PIECE_NAMES[kind]} não pode ir de {text[:2]} para {text[2:4]} (movimento impossível ou rei ficaria exposto)"


SAN_RE = re.compile(r"^([NBRQK])?([a-h])?([1-8])?x?([a-h][1-8])(?:=?([QRBNqrbn]))?$")
SAN_PIECES = {"N": 2, "B": 3, "R": 4, "Q": 5, "K": 6}


def san_to_uci_guess(board: Board, san: str):
    """UCI provável de um SAN ilegal, para explicar o motivo; None se não der para saber."""
    text = san.strip().replace("0", "O").rstrip("+#!?")
    if text in ("O-O", "O-O-O"):
        king = board.king_square(board.turn)
        return SQUARE_NAMES[king] + SQUARE_NAMES[king + (2 if text == "O-O" else -2)]
    m = SAN_RE.match(text)
    if not m:
        return None
    letter, file_, rank, dest, promo = m.groups()
    kind = SAN_PIECES[letter] if letter else PAWN
    to = square_index(dest)
    promo = (promo or "").lower()
    if kind == PAWN:
        step = 8 if board.turn == WHITE else -8
        if file_:  # captura de peão: exd6
            frm = to - step + (ord(file_) - ord(dest[0]))
            return SQUARE_NAMES[frm] + dest + promo if 0 <= frm < 64 else None
        for frm in (to - step, to - 2 * step):
            if 0 <= frm < 64 and board.piece_at(frm) == PAWN * board.turn:
                return SQUARE_NAMES[frm] + dest + promo
        return None
    sources = [sq for sq in range(64) if board.piece_at(sq) == kind * board.turn
               and (not file_ or SQUARE_NAMES[sq][0] == file_) and (not rank or SQUARE_NAMES[sq][1] == rank)]
    return SQUARE_NAMES[sources[0]] + dest if len(sources) == 1 else None


def pseudo_legal(board: Board, uci: str):
    """True/False pelo python-chess, ou None se ele não estiver instalado."""
    try:
        import chess
    except ImportError:
        return None
    return chess.Board(board.fen()).is_pseudo_legal(chess.Move.from_uci(uci))


def parse(board: Board, text: str) -> int:
    if UCI_RE.match(text.lower()):
        return board.parse_uci(text)
    return board.parse_san(text)


def state(board: Board) -> dict:
    outcome = board.outcome(claim_draw=False)
    claimable = board.outcome(claim_draw=True)
    return {
        "fen": board.fen(),
        "vez": color_name(board.turn),
        "xeque": board.is_check(),
        "xeque_mate": board.is_checkmate(),
        "afogamento": board.is_stalemate(),
        "fim_automatico": TERMINATIONS[outcome.termination] if outcome else None,
        "empate_reivindicavel": (TERMINATIONS[claimable.termination]
                                 if claimable and not outcome else None),
        "resultado": outcome.result() if outcome else None,
        "lances_legais": len(board.legal_moves()),
    }


def cross_check(board: Board) -> dict:
    try:
        import chess
    except ImportError:
        return {"disponivel": False}
    ref = chess.Board(board.fen())
    ours = sorted(move_to_uci(m) for m in board.legal_moves())
    theirs = sorted(m.uci() for m in ref.legal_moves)
    return {
        "disponivel": True,
        "lances_iguais": ours == theirs,
        "so_no_motor": sorted(set(ours) - set(theirs)),
        "so_no_python_chess": sorted(set(theirs) - set(ours)),
        "xeque_igual": board.is_check() == ref.is_check(),
        "mate_igual": board.is_checkmate() == ref.is_checkmate(),
    }


def run(fen: str, moves: list[str], list_moves: bool, cross: bool) -> dict:
    try:
        board = Board(fen)
    except ValueError as exc:
        return {"fen_valida": False, "erro": str(exc)}
    report: dict = {"fen_valida": True, "fen_inicial": board.fen(), "lances": []}
    for text in moves:
        try:
            move = parse(board, text)
        except ValueError:
            report["lances"].append({"entrada": text, "legal": False,
                                     "motivo": explain_illegal(board, text)})
            break
        report["lances"].append({"entrada": text, "legal": True, **describe_move(board, move)})
        board.push(move)
    report["posicao_final"] = state(board)
    if list_moves:
        report["lances_legais"] = sorted(board.san(m) for m in board.legal_moves())
    if cross:
        report["python_chess"] = cross_check(board)
    return report


def yes(flag) -> str:
    return "sim" if flag else "não"


def print_text(r: dict) -> None:
    if not r["fen_valida"]:
        print(f"FEN rejeitada pelo motor: {r['erro']}")
        return
    print(f"Posição inicial: {r['fen_inicial']}")
    for m in r["lances"]:
        if not m["legal"]:
            print(f"✗ {m['entrada']}: ILEGAL. {m['motivo']}")
            continue
        tags = [t for t, on in (
            ("captura", m["captura"]), ("en passant", m["en_passant"]),
            (f"roque {m['roque']}", m["roque"]), (f"promove a {m['promocao']}", m["promocao"]),
            ("xeque", m["da_xeque"])) if on]
        print(f"✓ {m['entrada']}: legal ({m['san']}, {m['peca']}{', ' + ', '.join(tags) if tags else ''})")
    s = r["posicao_final"]
    print(f"\nPosição final: {s['fen']}")
    print(f"Vez das {s['vez']} | xeque: {yes(s['xeque'])} | mate: {yes(s['xeque_mate'])} | "
          f"afogamento: {yes(s['afogamento'])} | lances legais: {s['lances_legais']}")
    if s["fim_automatico"]:
        print(f"Partida encerrada: {s['fim_automatico']} ({s['resultado']})")
    elif s["empate_reivindicavel"]:
        print(f"Empate pode ser reivindicado: {s['empate_reivindicavel']}")
    if "lances_legais" in r:
        print("Lances legais:", " ".join(r["lances_legais"]) or "(nenhum)")
    if "python_chess" in r:
        c = r["python_chess"]
        if not c["disponivel"]:
            print("Conferência com python-chess: biblioteca não instalada (pip install chess)")
        elif c["lances_iguais"] and c["xeque_igual"] and c["mate_igual"]:
            print("Conferência com python-chess: tudo igual")
        else:
            print(f"Conferência com python-chess: DIVERGÊNCIA {json.dumps(c, ensure_ascii=False)}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fen", default=STARTING_FEN)
    ap.add_argument("--lances", default="", help="lances separados por espaço, UCI ou SAN")
    ap.add_argument("--listar", action="store_true", help="lista os lances legais na posição final")
    ap.add_argument("--cruzar", action="store_true", help="confere com o python-chess")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    moves = [t for t in re.split(r"\s+", re.sub(r"\d+\.(\.\.)?", " ", args.lances)) if t]
    report = run(args.fen, moves, args.listar, args.cruzar)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_text(report)
    return 0 if report["fen_valida"] and all(m["legal"] for m in report["lances"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
