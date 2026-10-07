"""Tabelas pré-calculadas usadas pela geração de lances.

Casas são índices 0..63 com a1=0, b1=1, ..., h1=7, a2=8, ..., h8=63.
"""

import random

# Tipos de peça (o sinal indica a cor: positivo = brancas, negativo = pretas)
EMPTY = 0
PAWN, KNIGHT, BISHOP, ROOK, QUEEN, KING = 1, 2, 3, 4, 5, 6

WHITE, BLACK = 1, -1

# Direções: (delta de coluna, delta de linha). 0..3 ortogonais, 4..7 diagonais.
DIRECTIONS = [(0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (-1, 1), (1, -1), (-1, -1)]
ORTHOGONAL = (0, 1, 2, 3)
DIAGONAL = (4, 5, 6, 7)


def _on_board(f, r):
    return 0 <= f < 8 and 0 <= r < 8


def _build_rays():
    rays = [[None] * 64 for _ in range(8)]
    for d, (df, dr) in enumerate(DIRECTIONS):
        for sq in range(64):
            f, r = sq & 7, sq >> 3
            ray = []
            f, r = f + df, r + dr
            while _on_board(f, r):
                ray.append(r * 8 + f)
                f, r = f + df, r + dr
            rays[d][sq] = tuple(ray)
    return rays


def _build_steps(deltas):
    table = []
    for sq in range(64):
        f, r = sq & 7, sq >> 3
        table.append(tuple((r + dr) * 8 + (f + df) for df, dr in deltas if _on_board(f + df, r + dr)))
    return table


# RAYS[d][sq] -> casas a partir de sq (exclusive) na direção d, até a borda.
RAYS = _build_rays()

KNIGHT_ATTACKS = _build_steps([(1, 2), (2, 1), (2, -1), (1, -2), (-1, -2), (-2, -1), (-2, 1), (-1, 2)])
KING_ATTACKS = _build_steps([(0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (-1, 1), (1, -1), (-1, -1)])

# PAWN_ATTACKS[cor][sq] -> casas que um peão daquela cor em sq ataca.
PAWN_ATTACKS = {
    WHITE: _build_steps([(-1, 1), (1, 1)]),
    BLACK: _build_steps([(-1, -1), (1, -1)]),
}

# DIRECTION_BETWEEN[a][b] -> índice de direção de a para b se estiverem alinhadas, senão -1.
DIRECTION_BETWEEN = [[-1] * 64 for _ in range(64)]
# BETWEEN[a][b] -> frozenset das casas estritamente entre a e b (vazio se não alinhadas).
BETWEEN = [[frozenset()] * 64 for _ in range(64)]
for _a in range(64):
    for _d in range(8):
        _ray = RAYS[_d][_a]
        for _i, _b in enumerate(_ray):
            DIRECTION_BETWEEN[_a][_b] = _d
            BETWEEN[_a][_b] = frozenset(_ray[:_i])

# Máscara de direitos de roque perdidos quando uma peça sai de/chega em uma casa.
CASTLE_WK, CASTLE_WQ, CASTLE_BK, CASTLE_BQ = 1, 2, 4, 8
CASTLING_MASK = [15] * 64
CASTLING_MASK[4] = 15 & ~(CASTLE_WK | CASTLE_WQ)   # e1
CASTLING_MASK[0] = 15 & ~CASTLE_WQ                  # a1
CASTLING_MASK[7] = 15 & ~CASTLE_WK                  # h1
CASTLING_MASK[60] = 15 & ~(CASTLE_BK | CASTLE_BQ)  # e8
CASTLING_MASK[56] = 15 & ~CASTLE_BQ                 # a8
CASTLING_MASK[63] = 15 & ~CASTLE_BK                 # h8

# Zobrist: chaves de 64 bits com semente fixa, para resultados reprodutíveis.
_rng = random.Random(0x5EED_C4E55)
ZOBRIST_PIECE = [[_rng.getrandbits(64) for _ in range(64)] for _ in range(13)]  # índice = peça + 6
ZOBRIST_CASTLING = [_rng.getrandbits(64) for _ in range(16)]
ZOBRIST_EP_FILE = [_rng.getrandbits(64) for _ in range(8)]
ZOBRIST_BLACK_TO_MOVE = _rng.getrandbits(64)

FILE_NAMES = "abcdefgh"
RANK_NAMES = "12345678"
SQUARE_NAMES = [FILE_NAMES[s & 7] + RANK_NAMES[s >> 3] for s in range(64)]
PIECE_SYMBOLS = {PAWN: "p", KNIGHT: "n", BISHOP: "b", ROOK: "r", QUEEN: "q", KING: "k"}
SYMBOL_TO_PIECE = {v: k for k, v in PIECE_SYMBOLS.items()}


def square_index(name):
    """'e4' -> 28."""
    return RANK_NAMES.index(name[1]) * 8 + FILE_NAMES.index(name[0])
