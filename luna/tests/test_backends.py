"""Os dois backends devem dar à Luna exatamente as mesmas respostas."""

import random

import pytest

from luna.adapters import new_game
from luna.evaluation import evaluate
from luna.genome import Genome
from luna.match import MatchConfig, play_game
from luna.search import SearchConfig, Searcher
from luna.versions import load_version

pytest.importorskip("chess")
pytest.importorskip("chess_engine")

BACKENDS = ("python-chess", "chess_engine")

POSITIONS = [
    None,
    "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
    "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
    "rnbq1k1r/pp1Pbppp/2p5/8/2B5/8/PPP1NnPP/RNBQK2R w KQ - 1 8",
    "6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1",
]


def _snapshot(state):
    moves = sorted(state.uci(m) for m in state.legal_moves())
    by_uci = {state.uci(m): m for m in state.legal_moves()}
    return {
        "moves": moves,
        "check": state.is_check(),
        "mobility": (state.mobility(True), state.mobility(False)),
        "pieces": sorted(state.pieces()),
        "captures": {u: state.captured_piece(by_uci[u]) for u in moves},
        "movers": {u: state.moving_piece(by_uci[u]) for u in moves},
        "promo": {u: state.is_promotion(by_uci[u]) for u in moves},
        "gives_check": {u: state.gives_check(by_uci[u]) for u in moves},
        "repetition": state.is_repetition(),
        "san": {u: state.san(by_uci[u]) for u in moves},
    }


@pytest.mark.parametrize("fen", POSITIONS)
def test_backends_agree_on_positions(fen):
    a, b = (new_game(name, fen) for name in BACKENDS)
    assert _snapshot(a) == _snapshot(b)
    for g in [Genome.reference()] + [Genome.random(random.Random(i)) for i in range(5)]:
        # Igualdade exata: uma diferença no último dígito já muda o desempate entre lances.
        assert evaluate(a, g) == evaluate(b, g)


@pytest.mark.parametrize("fen", POSITIONS)
def test_pieces_come_in_square_order(fen):
    for name in BACKENDS:
        squares = [sq for sq, _, _ in new_game(name, fen).pieces()]
        assert squares == sorted(squares)


def test_evolved_genome_picks_same_move_on_both_backends():
    # Posição em que f1e1 e d2e3 empatavam e cada backend escolhia um lance.
    fen = "r1b3k1/ppp3p1/5r1p/2p1q3/4P3/1R1P4/P1PQ1PPP/5RK1 w - - 4 16"
    genome = load_version("luna-v1").genome
    moves = []
    for name in BACKENDS:
        state = new_game(name, fen)
        moves.append(state.uci(Searcher(genome, SearchConfig(depth=2)).choose_move(state)))
    assert moves[0] == moves[1]


@pytest.mark.parametrize("seed", range(4))
def test_same_game_with_evolved_genomes(seed):
    rng = random.Random(seed)
    white, black = Genome.random(rng, id="w"), Genome.random(rng, id="b")
    records = []
    for name in BACKENDS:
        cfg = MatchConfig(search=SearchConfig(depth=1, quiescence_depth=2, noise=5), max_plies=80, backend=name)
        records.append(play_game(white, black, cfg, seed=seed).to_dict())
    assert records[0] == records[1]


def test_backends_agree_along_random_games():
    rng = random.Random(11)
    for _ in range(5):
        a, b = (new_game(name) for name in BACKENDS)
        for _ in range(120):
            assert _snapshot(a) == _snapshot(b)
            oa, ob = a.outcome(), b.outcome()
            assert oa == ob
            if oa is not None:
                break
            move = rng.choice(sorted(a.uci(m) for m in a.legal_moves()))
            a.push(a.parse_uci(move))
            b.push(b.parse_uci(move))


def test_same_game_on_both_backends():
    records = []
    for name in BACKENDS:
        cfg = MatchConfig(search=SearchConfig(depth=1, quiescence_depth=2), max_plies=40, backend=name)
        records.append(play_game(Genome.reference(id="w"), Genome.reference(id="b"), cfg, seed=5))
    assert records[0].to_dict() == records[1].to_dict()
