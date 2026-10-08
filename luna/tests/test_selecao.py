"""Genes novos, catraca de promoção e jogadora oficial (análise de 2026-10-08)."""

import random

import chess
import pytest

from luna.adapters import new_game
from luna.evaluation import evaluate
from luna.evolution import EvolutionConfig
from luna.genome import GENE_SPECS, INTEGER_GENES, LEGACY_DEFAULTS, Genome, mutate
from luna.match import MatchConfig, play_game
from luna.openings import BOOK
from luna.player import LunaPlayer, official_factory
from luna.promotion import (
    PromotionConfig,
    elo_estimate,
    expected_score,
    llr,
    run_promotion_match,
)
from luna.search import INF, MATE_SCORE, MAX_PLY, SearchConfig, Searcher
from luna.versions import load_version, official_name, set_official

OLD_GENES = [n for n in GENE_SPECS if n not in LEGACY_DEFAULTS]


def genome(**changes):
    g = Genome.reference()
    g.genes.update({k: float(v) for k, v in changes.items()})
    return g


# ---------------------------------------------------------------- genoma


def test_old_genomes_get_legacy_values():
    old = {"genes": {n: GENE_SPECS[n][2] for n in OLD_GENES}}
    g = Genome.from_dict(old)
    for name, value in LEGACY_DEFAULTS.items():
        assert g.genes[name] == value


def test_integer_genes_are_rounded_and_mutation_moves_them():
    g = Genome({**Genome.reference().genes, "quiescence_depth": 3.6, "check_extension": 0.4})
    assert g.genes["quiescence_depth"] == 4.0 and g.genes["check_extension"] == 0.0
    rng = random.Random(1)
    base = genome(quiescence_depth=4, check_extension=1)
    for _ in range(50):
        child = mutate(base, rng, rate=1.0, scale=0.01)
        for name in INTEGER_GENES:
            assert child.genes[name] != base.genes[name]
            assert child.genes[name] == int(child.genes[name])


# ------------------------------------------------------------------ busca


def test_check_extension_sees_mate_after_a_check():
    # 1.Rc8+ Rxc8 2.Rxc8#: só a extensão no xeque deixa a profundidade 2 ver o mate.
    fen = "r5k1/5ppp/8/8/8/8/2R2PPP/2R3K1 w - - 0 1"
    scores = {}
    for ext in (0, 1):
        searcher = Searcher(genome(check_extension=ext), SearchConfig(depth=2))
        scores[ext] = searcher._negamax(new_game(fen=fen), 2, -INF, INF, 0, ext)
    assert scores[0] < MATE_SCORE - MAX_PLY
    assert scores[1] > MATE_SCORE - MAX_PLY


def test_search_config_overrides_genes_only_when_given():
    g = genome(quiescence_depth=6, contempt=120)
    s = Searcher(g, SearchConfig())
    assert (s.quiescence_depth, s.contempt) == (6, 120)
    s = Searcher(g, SearchConfig(quiescence_depth=0, contempt=10))
    assert (s.quiescence_depth, s.contempt) == (0, 10)


def test_old_configs_let_search_genes_evolve():
    d = EvolutionConfig().to_dict()
    d["match"]["search"].update(quiescence_depth=4, contempt=50.0)
    search = EvolutionConfig.from_dict(d).match.search
    assert search.quiescence_depth is None and search.contempt is None
    d["match"]["search"].update(quiescence_depth=2)
    assert EvolutionConfig.from_dict(d).match.search.quiescence_depth == 2


# -------------------------------------------------------------- avaliação


def test_mop_up_pushes_losing_king_to_the_edge():
    edge = new_game(fen="7k/8/8/8/8/8/8/R5K1 w - - 0 1")
    center = new_game(fen="8/8/8/4k3/8/8/8/R5K1 w - - 0 1")
    on = genome(king_edge=20, king_proximity=0)
    off = genome(king_edge=0, king_proximity=0)
    gain_on = evaluate(edge, on) - evaluate(center, on)
    gain_off = evaluate(edge, off) - evaluate(center, off)
    assert gain_on - gain_off == pytest.approx(20 * 6)


def test_mop_up_rewards_king_proximity():
    near = new_game(fen="7k/8/6K1/8/8/8/8/R7 w - - 0 1")
    far = new_game(fen="7k/8/8/8/8/8/8/R5K1 w - - 0 1")
    g = genome(king_edge=0, king_proximity=10, pst_weight=0, mobility=0)
    # Distância entre os reis: 3 casas perto, 8 longe.
    assert evaluate(near, g) - evaluate(far, g) == pytest.approx(10 * (8 - 3))


def test_passed_pawn_rank_grows_with_advance():
    seventh = new_game(fen="4k3/P7/8/8/8/8/8/4K3 w - - 0 1")
    third = new_game(fen="4k3/8/8/8/8/P7/8/4K3 w - - 0 1")
    base = {"pst_weight": 0, "king_edge": 0, "king_proximity": 0, "passed_pawn": 0}
    on, off = genome(passed_pawn_rank=6, **base), genome(passed_pawn_rank=0, **base)
    assert evaluate(seventh, off) == evaluate(third, off)
    assert evaluate(seventh, on) - evaluate(third, on) == pytest.approx(6 * (36 - 4) / 6)


def test_open_file_next_to_king_is_penalised():
    closed = new_game(fen="rn1qk2r/pppppppp/8/8/8/8/PPPPPPPP/RN1Q2K1 w - - 0 1")
    opened = new_game(fen="rn1qk2r/pppppppp/8/8/8/8/PPPPP1PP/RN1Q2K1 w - - 0 1")
    on, off = genome(king_open_file=30), genome(king_open_file=0)
    extra = (evaluate(closed, on) - evaluate(opened, on)) - (
        evaluate(closed, off) - evaluate(opened, off)
    )
    assert extra == pytest.approx(30)


# --------------------------------------------------------------- aberturas


def test_book_lines_are_legal_and_games_start_with_them():
    assert len(BOOK) == 40
    for line in BOOK:
        state = new_game()
        for uci in line:
            state.push(state.parse_uci(uci))
    cfg = MatchConfig(search=SearchConfig(depth=1, quiescence_depth=0), max_plies=20)
    rec = play_game(Genome.reference(), Genome.reference(), cfg, seed=3, opening=BOOK[2])
    assert rec.moves[: len(BOOK[2])] == list(BOOK[2])


# ---------------------------------------------------------------- catraca


def test_sequential_test_math():
    assert expected_score(0) == 0.5
    assert expected_score(30) == pytest.approx(0.5431, abs=1e-4)
    assert llr([0.75, 1.0, 0.5, 0.75] * 10, 0, 30) > 0
    assert llr([0.25, 0.0, 0.5, 0.25] * 10, 0, 30) < 0
    elo, err = elo_estimate([0.5, 0.75, 0.25, 0.5])
    assert elo == pytest.approx(0) and err > 0
    lower, upper = PromotionConfig().bounds
    assert lower == pytest.approx(-2.944, abs=1e-3) and upper == pytest.approx(2.944, abs=1e-3)


def test_promotion_match_rejects_a_weaker_candidate_and_is_reproducible():
    strong = genome(quiescence_depth=2)
    weak = Genome({**strong.genes, "queen": 700, "rook": 350, "pst_weight": 0, "mobility": 0})
    weak.id = "fraca"
    cfg = PromotionConfig(depth=1, max_games=80, max_plies=60, batch_pairs=8)
    first = run_promotion_match(weak, strong, cfg, workers=1, log=lambda _: None)
    assert first.games % 2 == 0 and first.games <= 80
    assert first.wins + first.draws + first.losses == first.games
    assert not first.promoted
    again = run_promotion_match(weak, strong, cfg, workers=2, log=lambda _: None)
    assert again.to_dict() == first.to_dict()


# ---------------------------------------------------------- jogadora oficial


def test_player_keeps_the_game_history():
    player = LunaPlayer(Genome.reference(), depth=1)
    board = chess.Board()
    opponent = random.Random(7)
    for _ in range(6):
        legal = [m.uci() for m in board.legal_moves]
        board.push_uci(player.choose_move(board.fen(), legal))
        assert player._state.ply == board.ply()
        board.push(opponent.choice(list(board.legal_moves)))
    # Uma FEN que não continua a partida faz a jogadora recomeçar dela.
    fen = "4k3/8/8/8/8/8/8/R3K3 w - - 0 1"
    player.choose_move(fen, [m.uci() for m in chess.Board(fen).legal_moves])
    assert player._state.ply == 1


def test_player_sees_repetitions_from_the_history():
    # Os cavalos vão e voltam. Só com o histórico a posição depois do 6º meio-lance
    # aparece como repetição; com a FEN sozinha ela pareceria nova.
    moves = "g1f3 g8f6 f3g1 f6g8 g1f3 g8f6".split()
    player = LunaPlayer(Genome.reference(), depth=1)
    state = new_game()
    for uci in moves[:-1]:  # até o último lance "da Luna"
        state.push(state.parse_uci(uci))
    player._state = state
    board = chess.Board()
    for uci in moves:
        board.push_uci(uci)
    followed = player._follow(board.fen())
    assert followed.ply == 6 and followed.is_repetition()
    assert not new_game(fen=board.fen()).is_repetition()


def test_official_player_uses_depth_three():
    name = official_name()
    assert load_version(name).name == name
    player = official_factory()
    assert player.searcher.config.depth == 3 and player.searcher.config.noise == 0.0
    with pytest.raises(FileNotFoundError):
        set_official("nao-existe")
