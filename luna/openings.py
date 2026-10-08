"""Livro de 40 aberturas equilibradas da teoria corrente (6 a 8 meios-lances).

É o livro da análise do critério de seleção de 2026-10-08
(``analises/criterio-selecao/scripts/livro.py``), convertido para UCI. Jogar a
mesma abertura duas vezes com as cores trocadas faz a vantagem da abertura entrar
com sinal oposto nas duas partidas e se cancelar no par: é a técnica de números
aleatórios comuns (Glasserman e Yao, 1992, Management Science 38(6):884-908).
"""

# fmt: off
BOOK: tuple[tuple[str, ...], ...] = tuple(tuple(line.split()) for line in (
    "e2e4 e7e5 g1f3 b8c6 f1b5 a7a6",  # e4 e5 Nf3 Nc6 Bb5 a6
    "e2e4 e7e5 g1f3 b8c6 f1c4 f8c5",  # e4 e5 Nf3 Nc6 Bc4 Bc5
    "e2e4 c7c5 g1f3 d7d6 d2d4 c5d4 f3d4 g8f6",  # e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6
    "e2e4 c7c5 g1f3 b8c6 d2d4 c5d4 f3d4 g7g6",  # e4 c5 Nf3 Nc6 d4 cxd4 Nxd4 g6
    "e2e4 c7c5 b1c3 b8c6 g2g3 g7g6",  # e4 c5 Nc3 Nc6 g3 g6
    "e2e4 e7e6 d2d4 d7d5 b1c3 g8f6",  # e4 e6 d4 d5 Nc3 Nf6
    "e2e4 e7e6 d2d4 d7d5 e4e5 c7c5",  # e4 e6 d4 d5 e5 c5
    "e2e4 c7c6 d2d4 d7d5 b1c3 d5e4 c3e4 c8f5",  # e4 c6 d4 d5 Nc3 dxe4 Nxe4 Bf5
    "e2e4 d7d5 e4d5 d8d5 b1c3 d5a5",  # e4 d5 exd5 Qxd5 Nc3 Qa5
    "e2e4 d7d6 d2d4 g8f6 b1c3 g7g6",  # e4 d6 d4 Nf6 Nc3 g6
    "e2e4 g8f6 e4e5 f6d5 d2d4 d7d6",  # e4 Nf6 e5 Nd5 d4 d6
    "e2e4 e7e5 g1f3 g8f6 f3e5 d7d6",  # e4 e5 Nf3 Nf6 Nxe5 d6
    "e2e4 e7e5 b1c3 g8f6 f2f4 d7d5",  # e4 e5 Nc3 Nf6 f4 d5
    "e2e4 e7e5 g1f3 b8c6 d2d4 e5d4 f3d4 g8f6",  # e4 e5 Nf3 Nc6 d4 exd4 Nxd4 Nf6
    "d2d4 d7d5 c2c4 e7e6 b1c3 g8f6",  # d4 d5 c4 e6 Nc3 Nf6
    "d2d4 d7d5 c2c4 c7c6 g1f3 g8f6",  # d4 d5 c4 c6 Nf3 Nf6
    "d2d4 d7d5 c2c4 d5c4 g1f3 g8f6",  # d4 d5 c4 dxc4 Nf3 Nf6
    "d2d4 g8f6 c2c4 g7g6 b1c3 f8g7 e2e4 d7d6",  # d4 Nf6 c4 g6 Nc3 Bg7 e4 d6
    "d2d4 g8f6 c2c4 e7e6 b1c3 f8b4",  # d4 Nf6 c4 e6 Nc3 Bb4
    "d2d4 g8f6 c2c4 e7e6 g1f3 b7b6",  # d4 Nf6 c4 e6 Nf3 b6
    "d2d4 g8f6 c2c4 c7c5 d4d5 e7e6",  # d4 Nf6 c4 c5 d5 e6
    "d2d4 f7f5 g2g3 g8f6 f1g2 g7g6",  # d4 f5 g3 Nf6 Bg2 g6
    "d2d4 d7d5 g1f3 g8f6 c1f4 e7e6",  # d4 d5 Nf3 Nf6 Bf4 e6
    "c2c4 e7e5 b1c3 g8f6 g1f3 b8c6",  # c4 e5 Nc3 Nf6 Nf3 Nc6
    "c2c4 c7c5 b1c3 b8c6 g2g3 g7g6",  # c4 c5 Nc3 Nc6 g3 g6
    "g1f3 d7d5 g2g3 g8f6 f1g2 e7e6",  # Nf3 d5 g3 Nf6 Bg2 e6
    "d2d4 g8f6 c2c4 g7g6 b1c3 d7d5",  # d4 Nf6 c4 g6 Nc3 d5
    "e2e4 c7c5 c2c3 g8f6 e4e5 f6d5",  # e4 c5 c3 Nf6 e5 Nd5
    "e2e4 e7e5 g1f3 b8c6 b1c3 g8f6",  # e4 e5 Nf3 Nc6 Nc3 Nf6
    "e2e4 c7c6 d2d4 d7d5 e4e5 c8f5",  # e4 c6 d4 d5 e5 Bf5
    "e2e4 e7e6 d2d4 d7d5 b1d2 c7c5",  # e4 e6 d4 d5 Nd2 c5
    "b2b3 e7e5 c1b2 b8c6 e2e3 g8f6",  # b3 e5 Bb2 Nc6 e3 Nf6
    "f2f4 d7d5 g1f3 g8f6 e2e3 g7g6",  # f4 d5 Nf3 Nf6 e3 g6
    "g2g3 d7d5 f1g2 e7e5 d2d3 g8f6",  # g3 d5 Bg2 e5 d3 Nf6
    "d2d4 e7e6 c2c4 f8b4 c1d2 b4d2",  # d4 e6 c4 Bb4+ Bd2 Bxd2+
    "e2e4 g7g6 d2d4 f8g7 b1c3 d7d6",  # e4 g6 d4 Bg7 Nc3 d6
    "d2d4 d7d5 c2c4 e7e6 b1c3 c7c5",  # d4 d5 c4 e6 Nc3 c5
    "e2e4 e7e5 g1f3 d7d6 d2d4 g8f6",  # e4 e5 Nf3 d6 d4 Nf6
    "e2e4 c7c5 g1f3 e7e6 d2d4 c5d4 f3d4 b8c6",  # e4 c5 Nf3 e6 d4 cxd4 Nxd4 Nc6
    "d2d4 g8f6 g1f3 e7e6 e2e3 c7c5",  # d4 Nf6 Nf3 e6 e3 c5
))
# fmt: on
