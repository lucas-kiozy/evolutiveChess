"""Tabuleiro, geração de lances legais e regras de fim de partida.

Representação
-------------
* ``board.squares``: lista de 64 inteiros, a1=0 ... h8=63. Positivo = peça branca,
  negativo = peça preta, 0 = vazio (ver ``PAWN``..``KING`` em ``tables``).
* Lances são inteiros: ``origem | destino << 6 | promocao << 12``. Use
  ``move_from``, ``move_to``, ``move_promotion``, ``move_to_uci`` e
  ``Board.parse_uci`` para trabalhar com eles.

A geração de lances é estritamente legal: calcula cravadas e xeques uma vez por
posição em vez de testar cada lance com faz/desfaz, o que a deixa bem mais rápida
em Python puro.
"""

from dataclasses import dataclass

from .tables import (
    BETWEEN, BISHOP, BLACK, CASTLE_BK, CASTLE_BQ, CASTLE_WK, CASTLE_WQ, CASTLING_MASK,
    DIRECTION_BETWEEN, EMPTY, KING, KING_ATTACKS, KNIGHT, KNIGHT_ATTACKS, PAWN,
    PAWN_ATTACKS, PIECE_SYMBOLS, QUEEN, RAYS, ROOK, SQUARE_NAMES, SYMBOL_TO_PIECE, WHITE,
    ZOBRIST_BLACK_TO_MOVE, ZOBRIST_CASTLING, ZOBRIST_EP_FILE, ZOBRIST_PIECE, square_index,
)

STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

PROMOTION_PIECES = (QUEEN, ROOK, BISHOP, KNIGHT)
_DIAG_SLIDERS = (BISHOP, QUEEN)
_ORTH_SLIDERS = (ROOK, QUEEN)


# --------------------------------------------------------------------------- lances

def make_move(from_sq, to_sq, promotion=0):
    return from_sq | (to_sq << 6) | (promotion << 12)


def move_from(move):
    return move & 63


def move_to(move):
    return (move >> 6) & 63


def move_promotion(move):
    """Tipo de peça da promoção (QUEEN, ROOK, BISHOP, KNIGHT) ou 0."""
    return move >> 12


def move_to_uci(move):
    promo = move >> 12
    uci = SQUARE_NAMES[move & 63] + SQUARE_NAMES[(move >> 6) & 63]
    return uci + PIECE_SYMBOLS[promo] if promo else uci


# --------------------------------------------------------------------------- resultado

@dataclass(frozen=True)
class Outcome:
    """Resultado de uma partida terminada.

    ``winner`` é ``WHITE`` (1), ``BLACK`` (-1) ou ``None`` em empate.
    ``termination`` é um de: ``checkmate``, ``stalemate``, ``insufficient_material``,
    ``seventyfive_moves``, ``fivefold_repetition``, ``fifty_moves``,
    ``threefold_repetition``.
    """

    winner: object
    termination: str

    def result(self):
        if self.winner == WHITE:
            return "1-0"
        if self.winner == BLACK:
            return "0-1"
        return "1/2-1/2"


# --------------------------------------------------------------------------- tabuleiro

class Board:
    """Posição de xadrez com histórico (para desfazer lances e detectar repetição).

    ``turn`` vale ``WHITE`` (1) ou ``BLACK`` (-1). Várias listas internas têm 3
    posições e são indexadas pela própria cor: ``x[1]`` é das brancas e ``x[-1]``
    (o último elemento) é das pretas.
    """

    __slots__ = ("squares", "turn", "castling", "ep_square", "halfmove_clock", "fullmove_number",
                 "_kings", "_hash", "_ep_key", "_in_check", "_checks", "_moves_made",
                 "_stack", "_hashes", "_legal")

    def __init__(self, fen=STARTING_FEN):
        self.set_fen(fen)

    # ------------------------------------------------------------------ FEN

    def set_fen(self, fen):
        parts = fen.split()
        if len(parts) < 4:
            raise ValueError(f"FEN inválida: {fen!r}")
        placement, side, castling, ep = parts[:4]
        halfmove = int(parts[4]) if len(parts) > 4 else 0
        fullmove = int(parts[5]) if len(parts) > 5 else 1

        squares = [EMPTY] * 64
        rows = placement.split("/")
        if len(rows) != 8:
            raise ValueError(f"FEN inválida: {fen!r}")
        for i, row in enumerate(rows):
            rank = 7 - i
            file = 0
            for ch in row:
                if ch.isdigit():
                    file += int(ch)
                else:
                    piece = SYMBOL_TO_PIECE.get(ch.lower())
                    if piece is None or file > 7:
                        raise ValueError(f"FEN inválida: {fen!r}")
                    squares[rank * 8 + file] = piece if ch.isupper() else -piece
                    file += 1
            if file != 8:
                raise ValueError(f"FEN inválida: {fen!r}")

        kings = [None, None, None]
        for sq, p in enumerate(squares):
            if p == KING or p == -KING:
                if kings[1 if p > 0 else -1] is not None:
                    raise ValueError("FEN com mais de um rei da mesma cor")
                kings[1 if p > 0 else -1] = sq
        if kings[1] is None or kings[-1] is None:
            raise ValueError("FEN sem rei")

        if side not in ("w", "b"):
            raise ValueError(f"FEN inválida: {fen!r}")
        rights = 0
        if castling != "-":
            for ch in castling:
                rights |= {"K": CASTLE_WK, "Q": CASTLE_WQ, "k": CASTLE_BK, "q": CASTLE_BQ}[ch]

        self.squares = squares
        self.turn = WHITE if side == "w" else BLACK
        self.castling = rights
        self.ep_square = -1 if ep == "-" else square_index(ep)
        self.halfmove_clock = halfmove
        self.fullmove_number = fullmove
        self._kings = kings
        self._ep_key = self._compute_ep_key()
        self._hash = self._compute_hash()
        self._in_check = self._attacked(kings[self.turn], -self.turn)
        self._checks = [0, 0, 0]
        self._moves_made = [0, 0, 0]
        self._stack = []
        self._hashes = [self._hash]
        self._legal = None

    def fen(self):
        rows = []
        for rank in range(7, -1, -1):
            row, empty = "", 0
            for file in range(8):
                p = self.squares[rank * 8 + file]
                if p == EMPTY:
                    empty += 1
                    continue
                if empty:
                    row += str(empty)
                    empty = 0
                sym = PIECE_SYMBOLS[abs(p)]
                row += sym.upper() if p > 0 else sym
            if empty:
                row += str(empty)
            rows.append(row)
        castling = "".join(ch for bit, ch in ((CASTLE_WK, "K"), (CASTLE_WQ, "Q"), (CASTLE_BK, "k"),
                                              (CASTLE_BQ, "q")) if self.castling & bit) or "-"
        ep = SQUARE_NAMES[self.ep_square] if self.ep_square >= 0 else "-"
        side = "w" if self.turn == WHITE else "b"
        return f"{'/'.join(rows)} {side} {castling} {ep} {self.halfmove_clock} {self.fullmove_number}"

    def copy(self):
        """Cópia independente, incluindo histórico (repetições continuam valendo)."""
        b = Board.__new__(Board)
        b.squares = self.squares[:]
        b.turn = self.turn
        b.castling = self.castling
        b.ep_square = self.ep_square
        b.halfmove_clock = self.halfmove_clock
        b.fullmove_number = self.fullmove_number
        b._kings = self._kings[:]
        b._hash = self._hash
        b._ep_key = self._ep_key
        b._in_check = self._in_check
        b._checks = self._checks[:]
        b._moves_made = self._moves_made[:]
        b._stack = self._stack[:]
        b._hashes = self._hashes[:]
        b._legal = self._legal
        return b

    # ------------------------------------------------------------------ hash

    def _compute_ep_key(self):
        """Só entra no hash se algum peão adversário puder, em tese, capturar en passant."""
        ep = self.ep_square
        if ep < 0:
            return 0
        pawn = PAWN * self.turn
        # Casas de onde um peão de quem joga atacaria ep.
        for s in PAWN_ATTACKS[-self.turn][ep]:
            if self.squares[s] == pawn:
                return ZOBRIST_EP_FILE[ep & 7]
        return 0

    def _compute_hash(self):
        h = 0
        for sq, p in enumerate(self.squares):
            if p:
                h ^= ZOBRIST_PIECE[p + 6][sq]
        h ^= ZOBRIST_CASTLING[self.castling] ^ self._ep_key
        if self.turn == BLACK:
            h ^= ZOBRIST_BLACK_TO_MOVE
        return h

    def key(self):
        """Hash Zobrist da posição (peças, vez, roques e en passant capturável)."""
        return self._hash

    # ------------------------------------------------------------------ ataques

    def _attacked(self, sq, by):
        """A casa ``sq`` é atacada por alguma peça da cor ``by``?"""
        squares = self.squares
        pawn = PAWN * by
        for s in PAWN_ATTACKS[-by][sq]:
            if squares[s] == pawn:
                return True
        knight = KNIGHT * by
        for s in KNIGHT_ATTACKS[sq]:
            if squares[s] == knight:
                return True
        king = KING * by
        for s in KING_ATTACKS[sq]:
            if squares[s] == king:
                return True
        queen = QUEEN * by
        rook = ROOK * by
        bishop = BISHOP * by
        for d in range(8):
            slider = rook if d < 4 else bishop
            for s in RAYS[d][sq]:
                p = squares[s]
                if p:
                    if p == queen or p == slider:
                        return True
                    break
        return False

    def is_attacked(self, sq, by):
        """Interface pública de ``_attacked`` (sq como índice 0..63, by como cor)."""
        return self._attacked(sq, by)

    # ------------------------------------------------------------------ geração de lances

    def legal_moves(self):
        """Lista com todos os lances legais da posição (inteiros)."""
        if self._legal is None:
            self._legal = self._generate_legal()
        return list(self._legal)

    def _generate_legal(self):
        squares = self.squares
        us = self.turn
        them = -us
        k = self._kings[us]
        moves = []
        append = moves.append

        # Cravadas e xeques por peças deslizantes, olhando a partir do rei.
        pinned = {}
        checkers = []
        for d in range(8):
            sliders = _ORTH_SLIDERS if d < 4 else _DIAG_SLIDERS
            own = -1
            for s in RAYS[d][k]:
                p = squares[s]
                if not p:
                    continue
                if p * us > 0:
                    if own >= 0:
                        break
                    own = s
                    continue
                if -p * us in sliders:
                    if own >= 0:
                        pinned[own] = d
                    else:
                        checkers.append(s)
                break
        enemy_knight = KNIGHT * them
        for s in KNIGHT_ATTACKS[k]:
            if squares[s] == enemy_knight:
                checkers.append(s)
        enemy_pawn = PAWN * them
        for s in PAWN_ATTACKS[us][k]:
            if squares[s] == enemy_pawn:
                checkers.append(s)

        # Rei: tira o rei do tabuleiro para que ele não "bloqueie" o raio que o ataca.
        squares[k] = EMPTY
        for t in KING_ATTACKS[k]:
            if squares[t] * us <= 0 and not self._attacked(t, them):
                append(k | t << 6)
        squares[k] = KING * us

        if len(checkers) > 1:
            return moves

        if checkers:
            c = checkers[0]
            target = BETWEEN[k][c] | {c}
        else:
            target = None
            # Roque (não pode estar em xeque, nem passar/chegar em casa atacada).
            rights = self.castling
            if us == WHITE:
                if (rights & CASTLE_WK and squares[7] == ROOK and not squares[5] and not squares[6]
                        and not self._attacked(5, them) and not self._attacked(6, them)):
                    append(4 | 6 << 6)
                if (rights & CASTLE_WQ and squares[0] == ROOK and not squares[1] and not squares[2]
                        and not squares[3] and not self._attacked(3, them) and not self._attacked(2, them)):
                    append(4 | 2 << 6)
            else:
                if (rights & CASTLE_BK and squares[63] == -ROOK and not squares[61] and not squares[62]
                        and not self._attacked(61, them) and not self._attacked(62, them)):
                    append(60 | 62 << 6)
                if (rights & CASTLE_BQ and squares[56] == -ROOK and not squares[57] and not squares[58]
                        and not squares[59] and not self._attacked(59, them) and not self._attacked(58, them)):
                    append(60 | 58 << 6)

        dir_from_king = DIRECTION_BETWEEN[k]
        forward = 8 * us
        start_rank = 1 if us == WHITE else 6
        promo_rank = 7 if us == WHITE else 0

        for s in range(64):
            p = squares[s] * us
            if p <= 0 or p == KING:
                continue
            pin = pinned.get(s, -1)
            if p == KNIGHT:
                if pin >= 0:
                    continue
                for t in KNIGHT_ATTACKS[s]:
                    if squares[t] * us <= 0 and (target is None or t in target):
                        append(s | t << 6)
            elif p == PAWN:
                candidates = []
                t = s + forward
                if not squares[t]:
                    candidates.append(t)
                    if s >> 3 == start_rank and not squares[t + forward]:
                        candidates.append(t + forward)
                for t in PAWN_ATTACKS[us][s]:
                    if squares[t] * us < 0:
                        candidates.append(t)
                for t in candidates:
                    if target is not None and t not in target:
                        continue
                    if pin >= 0 and dir_from_king[t] != pin:
                        continue
                    if t >> 3 == promo_rank:
                        for promo in PROMOTION_PIECES:
                            append(s | t << 6 | promo << 12)
                    else:
                        append(s | t << 6)
            else:
                if p == BISHOP:
                    dirs = (4, 5, 6, 7)
                elif p == ROOK:
                    dirs = (0, 1, 2, 3)
                else:
                    dirs = (0, 1, 2, 3, 4, 5, 6, 7)
                for d in dirs:
                    for t in RAYS[d][s]:
                        q = squares[t] * us
                        if q > 0:
                            break
                        if (target is None or t in target) and (pin < 0 or dir_from_king[t] == pin):
                            append(s | t << 6)
                        if q < 0:
                            break

        # En passant: raro e cheio de casos especiais (cravada horizontal etc.),
        # então valida simulando o lance.
        ep = self.ep_square
        if ep >= 0:
            pawn = PAWN * us
            captured_sq = ep - forward
            for s in PAWN_ATTACKS[them][ep]:
                if squares[s] != pawn:
                    continue
                squares[s] = EMPTY
                squares[captured_sq] = EMPTY
                squares[ep] = pawn
                legal = not self._attacked(k, them)
                squares[ep] = EMPTY
                squares[captured_sq] = -pawn
                squares[s] = pawn
                if legal:
                    append(s | ep << 6)

        return moves

    # ------------------------------------------------------------------ fazer / desfazer

    def push(self, move):
        """Aplica um lance (assume que é legal; use ``push_uci`` para validar)."""
        squares = self.squares
        us = self.turn
        frm = move & 63
        to = (move >> 6) & 63
        promo = move >> 12
        piece = squares[frm]
        captured = squares[to]

        self._stack.append((move, piece, captured, self.castling, self.ep_square, self._ep_key,
                            self.halfmove_clock, self._hash, self._in_check, self._legal))

        h = self._hash ^ ZOBRIST_CASTLING[self.castling] ^ self._ep_key ^ ZOBRIST_BLACK_TO_MOVE
        kind = piece * us

        h ^= ZOBRIST_PIECE[piece + 6][frm]
        squares[frm] = EMPTY
        if captured:
            h ^= ZOBRIST_PIECE[captured + 6][to]

        new_ep = -1
        if kind == PAWN:
            if to == self.ep_square:
                cap_sq = to - 8 * us
                h ^= ZOBRIST_PIECE[-piece + 6][cap_sq]
                squares[cap_sq] = EMPTY
            elif to - frm == 16 or frm - to == 16:
                new_ep = (frm + to) >> 1
            if promo:
                piece = promo * us
            self.halfmove_clock = 0
        elif kind == KING:
            self._kings[us] = to
            if to - frm == 2 or frm - to == 2:
                if to > frm:
                    r_from, r_to = frm + 3, frm + 1
                else:
                    r_from, r_to = frm - 4, frm - 1
                rook = squares[r_from]
                squares[r_from] = EMPTY
                squares[r_to] = rook
                h ^= ZOBRIST_PIECE[rook + 6][r_from] ^ ZOBRIST_PIECE[rook + 6][r_to]
            self.halfmove_clock = 0 if captured else self.halfmove_clock + 1
        else:
            self.halfmove_clock = 0 if captured else self.halfmove_clock + 1

        squares[to] = piece
        h ^= ZOBRIST_PIECE[piece + 6][to]

        self.castling &= CASTLING_MASK[frm] & CASTLING_MASK[to]
        self.ep_square = new_ep
        if us == BLACK:
            self.fullmove_number += 1
        self.turn = -us
        self._moves_made[us] += 1

        self._ep_key = self._compute_ep_key() if new_ep >= 0 else 0
        self._hash = h ^ ZOBRIST_CASTLING[self.castling] ^ self._ep_key
        self._hashes.append(self._hash)
        self._legal = None

        self._in_check = self._attacked(self._kings[-us], us)
        if self._in_check:
            self._checks[us] += 1

    def pop(self):
        """Desfaz o último lance e o devolve."""
        (move, piece, captured, castling, ep, ep_key, halfmove, h, in_check,
         legal) = self._stack.pop()
        squares = self.squares
        them = self.turn
        us = -them
        frm = move & 63
        to = (move >> 6) & 63

        if self._in_check:
            self._checks[us] -= 1
        self._moves_made[us] -= 1

        squares[frm] = piece
        squares[to] = captured
        kind = piece * us
        if kind == PAWN and to == ep:
            squares[to - 8 * us] = PAWN * them
        elif kind == KING:
            self._kings[us] = frm
            if to - frm == 2 or frm - to == 2:
                if to > frm:
                    r_from, r_to = frm + 3, frm + 1
                else:
                    r_from, r_to = frm - 4, frm - 1
                squares[r_from] = squares[r_to]
                squares[r_to] = EMPTY

        self.turn = us
        if us == BLACK:
            self.fullmove_number -= 1
        self.castling = castling
        self.ep_square = ep
        self._ep_key = ep_key
        self.halfmove_clock = halfmove
        self._hash = h
        self._in_check = in_check
        self._legal = legal
        self._hashes.pop()
        return move

    def parse_uci(self, uci):
        """Converte 'e2e4' / 'e7e8q' em lance, validando que é legal."""
        uci = uci.strip().lower()
        if len(uci) not in (4, 5):
            raise ValueError(f"Lance UCI inválido: {uci!r}")
        try:
            promo = SYMBOL_TO_PIECE[uci[4]] if len(uci) == 5 else 0
            move = make_move(square_index(uci[:2]), square_index(uci[2:4]), promo)
        except (KeyError, ValueError):
            raise ValueError(f"Lance UCI inválido: {uci!r}") from None
        if move not in self.legal_moves():
            raise ValueError(f"Lance ilegal: {uci}")
        return move

    def push_uci(self, uci):
        move = self.parse_uci(uci)
        self.push(move)
        return move

    # ------------------------------------------------------------------ informações sobre lances

    def is_capture(self, move):
        to = (move >> 6) & 63
        if self.squares[to]:
            return True
        return to == self.ep_square and self.squares[move & 63] * self.turn == PAWN

    def is_castling(self, move):
        frm, to = move & 63, (move >> 6) & 63
        return self.squares[frm] * self.turn == KING and abs(to - frm) == 2

    def gives_check(self, move):
        self.push(move)
        check = self._in_check
        self.pop()
        return check

    def san(self, move):
        """Notação algébrica padrão (ex.: 'Nf3', 'exd5', 'O-O', 'e8=Q+')."""
        frm, to, promo = move & 63, (move >> 6) & 63, move >> 12
        kind = self.squares[frm] * self.turn
        if kind == KING and abs(to - frm) == 2:
            san = "O-O" if to > frm else "O-O-O"
        else:
            capture = self.is_capture(move)
            if kind == PAWN:
                san = SQUARE_NAMES[frm][0] + "x" if capture else ""
            else:
                san = PIECE_SYMBOLS[kind].upper()
                rivals = [m & 63 for m in self.legal_moves()
                          if (m >> 6) & 63 == to and m & 63 != frm
                          and self.squares[m & 63] * self.turn == kind]
                if rivals:
                    if all(r & 7 != frm & 7 for r in rivals):
                        san += SQUARE_NAMES[frm][0]
                    elif all(r >> 3 != frm >> 3 for r in rivals):
                        san += SQUARE_NAMES[frm][1]
                    else:
                        san += SQUARE_NAMES[frm]
                if capture:
                    san += "x"
            san += SQUARE_NAMES[to]
            if promo:
                san += "=" + PIECE_SYMBOLS[promo].upper()
        self.push(move)
        if self._in_check:
            san += "#" if not self.legal_moves() else "+"
        self.pop()
        return san

    def parse_san(self, san):
        """Converte SAN em lance legal. Aceita '0-0', sufixos '+', '#', '!' e '?'."""
        wanted = san.strip().replace("0", "O").rstrip("+#!?")
        for move in self.legal_moves():
            if self.san(move).rstrip("+#") == wanted:
                return move
        raise ValueError(f"Lance SAN ilegal ou ambíguo: {san!r}")

    def push_san(self, san):
        move = self.parse_san(san)
        self.push(move)
        return move

    # ------------------------------------------------------------------ estado da partida

    @property
    def ply(self):
        """Quantos meios-lances foram jogados desde a posição inicial deste objeto."""
        return len(self._stack)

    @property
    def move_stack(self):
        """Lances jogados desde a posição inicial deste objeto, em ordem."""
        return [entry[0] for entry in self._stack]

    def peek(self):
        return self._stack[-1][0]

    def king_square(self, color):
        return self._kings[color]

    def piece_at(self, sq):
        return self.squares[sq]

    def moves_made(self, color):
        """Quantos lances a cor ``color`` já fez nesta partida."""
        return self._moves_made[color]

    def checks_given(self, color):
        """Quantos xeques a cor ``color`` já deu nesta partida (xeque-mate conta)."""
        return self._checks[color]

    def is_check(self):
        return self._in_check

    def is_checkmate(self):
        return self._in_check and not self._has_legal_move()

    def is_stalemate(self):
        return not self._in_check and not self._has_legal_move()

    def _has_legal_move(self):
        if self._legal is None:
            self._legal = self._generate_legal()
        return bool(self._legal)

    def is_insufficient_material(self):
        """Nenhum dos lados consegue dar mate (K x K, K+menor x K, só bispos da mesma cor)."""
        minors = []
        for sq, p in enumerate(self.squares):
            kind = abs(p)
            if kind in (PAWN, ROOK, QUEEN):
                return False
            if kind in (KNIGHT, BISHOP):
                minors.append((kind, sq))
        if len(minors) <= 1:
            return True
        if all(kind == BISHOP for kind, _ in minors):
            colors = {((sq & 7) + (sq >> 3)) & 1 for _, sq in minors}
            return len(colors) == 1
        return False

    def repetitions(self):
        """Quantas vezes a posição atual já ocorreu nesta partida, contando a atual."""
        h = self._hash
        hashes = self._hashes
        last = len(hashes) - 1
        first = max(0, last - self.halfmove_clock)
        return sum(1 for i in range(last, first - 1, -2) if hashes[i] == h)

    _repetitions = repetitions

    def is_fifty_moves(self):
        return self.halfmove_clock >= 100

    def is_seventyfive_moves(self):
        return self.halfmove_clock >= 150

    def is_threefold_repetition(self):
        return self.repetitions() >= 3

    def is_fivefold_repetition(self):
        return self.repetitions() >= 5

    def outcome(self, claim_draw=True):
        """Resultado da partida, ou ``None`` se ela continua.

        Com ``claim_draw=True`` (padrão, adequado para partidas automáticas) a regra
        dos 50 lances e a tripla repetição encerram a partida. Com ``False`` só valem
        os empates automáticos da FIDE (75 lances, quíntupla repetição).
        """
        if not self._has_legal_move():
            if self._in_check:
                return Outcome(-self.turn, "checkmate")
            return Outcome(None, "stalemate")
        if self.is_insufficient_material():
            return Outcome(None, "insufficient_material")
        if self.is_seventyfive_moves():
            return Outcome(None, "seventyfive_moves")
        if self.is_fivefold_repetition():
            return Outcome(None, "fivefold_repetition")
        if claim_draw:
            if self.is_fifty_moves():
                return Outcome(None, "fifty_moves")
            if self.is_threefold_repetition():
                return Outcome(None, "threefold_repetition")
        return None

    def is_game_over(self, claim_draw=True):
        return self.outcome(claim_draw) is not None

    # ------------------------------------------------------------------ exibição

    def __str__(self):
        lines = []
        for rank in range(7, -1, -1):
            row = []
            for file in range(8):
                p = self.squares[rank * 8 + file]
                if not p:
                    row.append(".")
                else:
                    sym = PIECE_SYMBOLS[abs(p)]
                    row.append(sym.upper() if p > 0 else sym)
            lines.append(" ".join(row))
        return "\n".join(lines)

    def __repr__(self):
        return f"Board({self.fen()!r})"


def perft(board, depth):
    """Conta as folhas da árvore de lances legais até ``depth`` (teste padrão de geradores)."""
    if depth == 0:
        return 1
    moves = board._generate_legal() if board._legal is None else board._legal
    if depth == 1:
        return len(moves)
    total = 0
    for move in moves:
        board.push(move)
        total += perft(board, depth - 1)
        board.pop()
    return total
