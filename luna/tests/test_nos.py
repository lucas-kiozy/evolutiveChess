"""Limite de nós por lance (revisão do AG de 2026-11-28): treino reproduzível."""

from luna.adapters import new_game
from luna.genome import Genome
from luna.search import SearchConfig, Searcher

MIDDLEGAME = "r1bq1rk1/pp2bppp/2n1pn2/3p4/2PP4/2N1PN2/PP1B1PPP/R2QKB1R w KQ - 0 9"


def _search(config: SearchConfig):
    state = new_game("python-chess", MIDDLEGAME)
    searcher = Searcher(Genome.reference(), config)
    move = searcher.choose_move(state)
    return state, searcher, move


def test_node_limit_stops_the_search_and_still_plays():
    state, searcher, move = _search(SearchConfig(depth=8, node_limit=3000))
    assert move in state.legal_moves() and searcher.last_score is not None
    assert state.fen() == new_game("python-chess", MIDDLEGAME).fen()
    # A camada 1 sempre termina; depois dela, no máximo o limite (mais a camada 1).
    assert searcher.nodes <= 3000 + 2000
    assert searcher._node_cap is None


def test_node_limit_is_reproducible():
    """Mesma configuração e mesma semente: mesmo lance e mesmos nós, em qualquer máquina."""
    runs = [_search(SearchConfig(depth=6, node_limit=4000)) for _ in range(2)]
    (_, s1, m1), (_, s2, m2) = runs
    assert m1 == m2 and s1.nodes == s2.nodes and s1.last_score == s2.last_score


def test_a_large_node_limit_picks_the_fixed_depth_move():
    fixed = _search(SearchConfig(depth=2, quiescence_depth=2))
    limited = _search(SearchConfig(depth=2, quiescence_depth=2, node_limit=10**9))
    assert fixed[2] == limited[2] and fixed[1].last_score == limited[1].last_score


def test_node_limit_round_trips_through_dict():
    config = SearchConfig.from_dict({"depth": 3, "node_limit": 1234})
    assert config.node_limit == 1234
    assert SearchConfig.from_dict({"depth": 3}).node_limit is None


def test_mate_in_one_is_found_with_a_node_limit():
    state = new_game("python-chess", "6k1/5ppp/8/8/8/8/5PPP/R5K1 w - - 0 1")
    searcher = Searcher(Genome.reference(), SearchConfig(depth=6, node_limit=500))
    assert state.uci(searcher.choose_move(state)) == "a1a8"
