"""Tabela de transposição, killer e history: mesmo valor minimax, menos nós."""

import pytest

from luna.adapters import new_game
from luna.genome import Genome
from luna.search import SearchConfig, Searcher

FENS = [
    None,
    "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3",
    "r2q1rk1/ppp2ppp/2np1n2/2b1p1B1/2B1P1b1/2NP1N2/PPP2PPP/R2Q1RK1 w - - 4 8",
    "8/5pk1/6p1/8/3R4/6P1/5PKP/3r4 w - - 0 40",
]


def _search(fen, heuristics, backend="chess_engine", depth=3, **kw):
    state = new_game(backend, fen)
    searcher = Searcher(Genome.reference(), SearchConfig(depth=depth, heuristics=heuristics, **kw))
    move = searcher.choose_move(state)
    return state.uci(move), searcher.last_score, searcher.nodes, state.fen()


@pytest.mark.parametrize("fen", FENS)
def test_mesmo_lance_e_escore_com_menos_nos(fen):
    old = _search(fen, heuristics=False)
    new = _search(fen, heuristics=True)
    assert new[:2] == old[:2]
    assert new[2] <= old[2]
    assert new[3] == old[3]  # a busca devolve o estado como recebeu


def test_reduz_a_arvore_no_meio_jogo():
    old = _search(FENS[2], heuristics=False)
    new = _search(FENS[2], heuristics=True)
    assert new[2] < 0.8 * old[2]


def test_python_chess_igual_ao_chess_engine():
    pytest.importorskip("chess")
    for fen in FENS[:3]:
        assert _search(fen, True, "python-chess")[:2] == _search(fen, True, "chess_engine")[:2]


def test_mate_em_um_com_tabela():
    fen = "6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1"
    move, score, _, _ = _search(fen, True, depth=3)
    assert move == "d1d8"
    assert score > 90_000


def test_com_limite_de_tempo():
    move, score, _, fen = _search(FENS[2], True, depth=4, time_limit=60.0)
    assert (move, score) == _search(FENS[2], False, depth=4)[:2]
    assert fen == FENS[2]


def test_configuracao_salva_e_lida():
    assert SearchConfig.from_dict({"heuristics": False}).heuristics is False
    assert SearchConfig.from_dict({}).heuristics is True
