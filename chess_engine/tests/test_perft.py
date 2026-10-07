"""Perft: contagem de nós da árvore de lances legais comparada com valores de
referência publicados (https://www.chessprogramming.org/Perft_Results).

Qualquer erro em roque, en passant, promoção, cravadas ou xeques muda esses
números, então este é o teste mais forte de que todas as regras estão certas.
Os casos mais profundos são marcados como ``slow`` e só rodam com ``CHESS_SLOW=1``.
"""

import pytest

from chess_engine import Board, perft

START = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
KIWIPETE = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"
POSITION_3 = "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1"
POSITION_4 = "r3k2r/Pppp1ppp/1b3nbN/nP6/BBP1P3/q4N2/Pp1P2PP/R2Q1RK1 w kq - 0 1"
POSITION_4_MIRRORED = "r2q1rk1/pP1p2pp/Q4n2/bbp1p3/Np6/1B3NBn/pPPP1PPP/R3K2R b KQ - 0 1"
POSITION_5 = "rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8"
POSITION_6 = "r4rk1/1pp1qppp/p1np1n2/2b1p1B1/2B1P1b1/P1NP1N2/1PP1QPPP/R4RK1 w - - 0 10"

CASES = [
    (START, [20, 400, 8902, 197281]),
    (KIWIPETE, [48, 2039, 97862]),
    (POSITION_3, [14, 191, 2812, 43238]),
    (POSITION_4, [6, 264, 9467]),
    (POSITION_4_MIRRORED, [6, 264, 9467]),
    (POSITION_5, [44, 1486, 62379]),
    (POSITION_6, [46, 2079, 89890]),
    # Casos táticos de en passant, promoção e roque (conjunto de Martin Sedlak).
    ("3k4/3p4/8/K1P4r/8/8/8/8 b - - 0 1", [18, 92, 1670, 10138]),          # ep descobrindo xeque
    ("8/8/4k3/8/2p5/8/B2P2K1/8 w - - 0 1", [13, 102, 1266, 10276]),        # ep cravado
    ("8/8/1k6/2b5/2pP4/8/5K2/8 b - d3 0 1", [15, 126, 1928, 13931]),       # ep dá xeque
    ("5k2/8/8/8/8/8/8/4K2R w K - 0 1", [15, 66, 1198, 6399]),               # roque curto dá xeque
    ("3k4/8/8/8/8/8/8/R3K3 w Q - 0 1", [16, 71, 1286, 7418]),               # roque longo dá xeque
    ("r3k2r/1b4bq/8/8/8/8/7B/R3K2R w KQkq - 0 1", [26, 1141, 27826]),      # roque perde direitos
    ("r3k2r/8/3Q4/8/8/5q2/8/R3K2R b KQkq - 0 1", [44, 1494, 50509]),       # roque impedido
    ("2K2r2/4P3/8/8/8/8/8/3k4 w - - 0 1", [11, 133, 1442, 19174]),          # promoção para fugir
    ("8/8/1P2K3/8/2n5/1q6/8/5k2 b - - 0 1", [29, 165, 5160]),              # descoberta
    ("4k3/1P6/8/8/8/8/K7/8 w - - 0 1", [9, 40, 472, 2661]),                 # subpromoção
    ("8/P1k5/K7/8/8/8/8/8 w - - 0 1", [6, 27, 273, 1329]),                  # subpromoção a cavalo
    ("K1k5/8/P7/8/8/8/8/8 w - - 0 1", [2, 6, 13, 63, 382]),                 # afogamento
    ("8/k1P5/8/1K6/8/8/8/8 w - - 0 1", [10, 25, 268, 926]),                 # afogamento e mate
    ("8/8/2k5/5q2/5n2/8/5K2/8 b - - 0 1", [37, 183, 6559]),                 # xeque-mate
]


@pytest.mark.parametrize("fen,expected", CASES, ids=[f"{i}" for i in range(len(CASES))])
def test_perft(fen, expected):
    board = Board(fen)
    for depth, nodes in enumerate(expected, start=1):
        assert perft(board, depth) == nodes, f"profundidade {depth}"
    assert board.fen() == Board(fen).fen(), "perft deve deixar a posição intacta"


SLOW_CASES = [
    (START, 5, 4865609),
    (KIWIPETE, 4, 4085603),
    (POSITION_3, 5, 674624),
    (POSITION_4, 4, 422333),
    (POSITION_5, 4, 2103487),
    (POSITION_6, 4, 3894594),
]


@pytest.mark.slow
@pytest.mark.parametrize("fen,depth,nodes", SLOW_CASES)
def test_perft_deep(fen, depth, nodes):
    assert perft(Board(fen), depth) == nodes
