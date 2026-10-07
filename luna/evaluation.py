"""Função de avaliação parametrizada pelo genoma.

Pontuação em centipeões do ponto de vista de quem vai jogar. As tabelas
peça-casa são as da "Simplified Evaluation Function" de Tomasz Michniewski
(Chess Programming Wiki), multiplicadas pelo gene ``pst_weight``.
"""

from __future__ import annotations

from luna.game_interface import GameState
from luna.genome import Genome

# Tabelas do ponto de vista das brancas, linha 8 primeiro (como num diagrama).
_PST_RAW = {
    "P": [
        0, 0, 0, 0, 0, 0, 0, 0,
        50, 50, 50, 50, 50, 50, 50, 50,
        10, 10, 20, 30, 30, 20, 10, 10,
        5, 5, 10, 25, 25, 10, 5, 5,
        0, 0, 0, 20, 20, 0, 0, 0,
        5, -5, -10, 0, 0, -10, -5, 5,
        5, 10, 10, -20, -20, 10, 10, 5,
        0, 0, 0, 0, 0, 0, 0, 0,
    ],
    "N": [
        -50, -40, -30, -30, -30, -30, -40, -50,
        -40, -20, 0, 0, 0, 0, -20, -40,
        -30, 0, 10, 15, 15, 10, 0, -30,
        -30, 5, 15, 20, 20, 15, 5, -30,
        -30, 0, 15, 20, 20, 15, 0, -30,
        -30, 5, 10, 15, 15, 10, 5, -30,
        -40, -20, 0, 5, 5, 0, -20, -40,
        -50, -40, -30, -30, -30, -30, -40, -50,
    ],
    "B": [
        -20, -10, -10, -10, -10, -10, -10, -20,
        -10, 0, 0, 0, 0, 0, 0, -10,
        -10, 0, 5, 10, 10, 5, 0, -10,
        -10, 5, 5, 10, 10, 5, 5, -10,
        -10, 0, 10, 10, 10, 10, 0, -10,
        -10, 10, 10, 10, 10, 10, 10, -10,
        -10, 5, 0, 0, 0, 0, 5, -10,
        -20, -10, -10, -10, -10, -10, -10, -20,
    ],
    "R": [
        0, 0, 0, 0, 0, 0, 0, 0,
        5, 10, 10, 10, 10, 10, 10, 5,
        -5, 0, 0, 0, 0, 0, 0, -5,
        -5, 0, 0, 0, 0, 0, 0, -5,
        -5, 0, 0, 0, 0, 0, 0, -5,
        -5, 0, 0, 0, 0, 0, 0, -5,
        -5, 0, 0, 0, 0, 0, 0, -5,
        0, 0, 0, 5, 5, 0, 0, 0,
    ],
    "Q": [
        -20, -10, -10, -5, -5, -10, -10, -20,
        -10, 0, 0, 0, 0, 0, 0, -10,
        -10, 0, 5, 5, 5, 5, 0, -10,
        -5, 0, 5, 5, 5, 5, 0, -5,
        0, 0, 5, 5, 5, 5, 0, -5,
        -10, 5, 5, 5, 5, 5, 0, -10,
        -10, 0, 5, 0, 0, 0, 0, -10,
        -20, -10, -10, -5, -5, -10, -10, -20,
    ],
    "K": [  # meio-jogo
        -30, -40, -40, -50, -50, -40, -40, -30,
        -30, -40, -40, -50, -50, -40, -40, -30,
        -30, -40, -40, -50, -50, -40, -40, -30,
        -30, -40, -40, -50, -50, -40, -40, -30,
        -20, -30, -30, -40, -40, -30, -30, -20,
        -10, -20, -20, -20, -20, -20, -20, -10,
        20, 20, 0, 0, 0, 0, 20, 20,
        20, 30, 10, 0, 0, 10, 30, 20,
    ],
    "K_END": [  # final
        -50, -40, -30, -20, -20, -30, -40, -50,
        -30, -20, -10, 0, 0, -10, -20, -30,
        -30, -10, 20, 30, 30, 20, -10, -30,
        -30, -10, 30, 40, 40, 30, -10, -30,
        -30, -10, 30, 40, 40, 30, -10, -30,
        -30, -10, 20, 30, 30, 20, -10, -30,
        -30, -30, 0, 0, 0, 0, -30, -30,
        -50, -30, -30, -30, -30, -30, -30, -50,
    ],
}


def _to_square_index(table: list[int]) -> list[int]:
    """Converte a tabela de diagrama (a8..h1) para índice de casa a1=0..h8=63."""
    out = [0] * 64
    for i, v in enumerate(table):
        rank = 7 - i // 8
        file = i % 8
        out[rank * 8 + file] = v
    return out


PST_WHITE = {k: _to_square_index(v) for k, v in _PST_RAW.items()}
# Para as pretas espelha-se a linha: casa s das pretas equivale a s ^ 56 das brancas.
PST_BLACK = {k: [v[s ^ 56] for s in range(64)] for k, v in PST_WHITE.items()}

PIECE_GENE = {"P": "pawn", "N": "knight", "B": "bishop", "R": "rook", "Q": "queen"}

MATE_SCORE = 100_000


def evaluate(state: GameState, genome: Genome) -> float:
    """Avaliação estática do ponto de vista do lado que vai jogar."""
    g = genome.genes
    material = 0.0
    pst = 0.0
    bishops = [0, 0]  # [pretas, brancas]
    pawn_files: list[list[int]] = [[0] * 8, [0] * 8]
    pawns: list[list[int]] = [[], []]
    rooks: list[list[int]] = [[], []]
    kings = [0, 0]
    non_pawn_material = 0.0

    for square, piece, white in state.pieces():
        sign = 1 if white else -1
        side = 1 if white else 0
        if piece == "K":
            kings[side] = square
            continue
        value = g[PIECE_GENE[piece]]
        material += sign * value
        table = PST_WHITE if white else PST_BLACK
        pst += sign * table[piece][square]
        if piece == "P":
            pawn_files[side][square & 7] += 1
            pawns[side].append(square)
        else:
            non_pawn_material += value
            if piece == "B":
                bishops[side] += 1
            elif piece == "R":
                rooks[side].append(square)

    endgame = non_pawn_material <= 2 * g["rook"] + g["bishop"]
    king_table = "K_END" if endgame else "K"
    pst += PST_WHITE[king_table][kings[1]] - PST_BLACK[king_table][kings[0]]

    score = material + g["pst_weight"] * pst

    # Par de bispos
    score += g["bishop_pair"] * ((bishops[1] >= 2) - (bishops[0] >= 2))

    # Estrutura de peões
    for side, sign in ((1, 1), (0, -1)):
        files = pawn_files[side]
        enemy_files = pawn_files[1 - side]
        doubled = sum(c - 1 for c in files if c > 1)
        isolated = 0
        for f, c in enumerate(files):
            if c and not ((f > 0 and files[f - 1]) or (f < 7 and files[f + 1])):
                isolated += c
        passed_bonus = 0.0
        for sq in pawns[side]:
            if _is_passed(sq, side, pawns[1 - side]):
                rank = sq >> 3
                advance = rank if side == 1 else 7 - rank  # 1..6
                passed_bonus += g["passed_pawn"] * advance / 6.0
        rook_bonus = 0
        for sq in rooks[side]:
            f = sq & 7
            if files[f] == 0:
                rook_bonus += 1 if enemy_files[f] else 2  # semiaberta = meio bônus
        shield = 0 if endgame else _king_shield(kings[side], side, pawns[side])
        score += sign * (
            -g["doubled_pawn"] * doubled
            - g["isolated_pawn"] * isolated
            + passed_bonus
            + g["rook_open_file"] * rook_bonus / 2.0
            + g["king_shield"] * shield
        )

    if g["mobility"]:
        score += g["mobility"] * (state.mobility(True) - state.mobility(False))

    # check_bonus: a posição em que o lado a jogar está em xeque vale menos para ele.
    if g["check_bonus"] and state.is_check():
        score -= g["check_bonus"] if state.white_to_move else -g["check_bonus"]

    return score if state.white_to_move else -score


def _is_passed(square: int, side: int, enemy_pawns: list[int]) -> bool:
    file, rank = square & 7, square >> 3
    for e in enemy_pawns:
        ef, er = e & 7, e >> 3
        if abs(ef - file) <= 1 and ((side == 1 and er > rank) or (side == 0 and er < rank)):
            return False
    return True


def _king_shield(king: int, side: int, own_pawns: list[int]) -> int:
    kf, kr = king & 7, king >> 3
    direction = 1 if side == 1 else -1
    count = 0
    for p in own_pawns:
        pf, pr = p & 7, p >> 3
        if abs(pf - kf) <= 1 and pr - kr in (direction, 2 * direction):
            count += 1
    return count
