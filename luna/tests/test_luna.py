import random

import pytest

from luna.adapters import new_game
from luna.evaluation import evaluate
from luna.evolution import EvolutionConfig, evolve, next_population, schedule
from luna.fitness import Stats, collect_stats, rank
from luna.game_interface import GameState
from luna.genome import GENE_SPECS, Genome, crossover, mutate
from luna.match import GameRecord, MatchConfig, play_game
from luna.search import SearchConfig, Searcher
from luna.storage import RunStorage


def record(white, black, winner, mate_moves=None, wc=0, bc=0, termination=None,
           wcap=None, bcap=None):
    return GameRecord(
        white_id=white, black_id=black, winner=winner,
        termination=termination or ("checkmate" if mate_moves else "max_plies"),
        plies=0, white_checks=wc, black_checks=bc, mate_moves=mate_moves,
        material_balance=0, moves=[], white_captures=wcap or {}, black_captures=bcap or {},
    )


def test_adapter_implements_interface():
    state = new_game()
    assert isinstance(state, GameState)
    assert len(state.legal_moves()) == 20
    state.push(state.parse_uci("e2e4"))
    assert not state.white_to_move and state.ply == 1
    assert state.uci(state.pop()) == "e2e4"


def test_unknown_backend():
    with pytest.raises(ValueError):
        new_game("nao-existe")


def test_evaluation_is_symmetric_at_start():
    assert evaluate(new_game(), Genome.reference()) == pytest.approx(0.0)


def test_evaluation_counts_material():
    # Brancas com uma dama a mais, brancas a jogar.
    state = new_game(fen="4k3/8/8/8/8/8/8/3QK3 w - - 0 1")
    assert evaluate(state, Genome.reference()) > 800


def test_search_finds_mate_in_one():
    # Mate do corredor: Ra8#.
    state = new_game(fen="6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1")
    move = Searcher(Genome.reference(), SearchConfig(depth=2)).choose_move(state)
    assert state.uci(move) == "a1a8"


@pytest.mark.parametrize("seed", range(10))
def test_search_finds_mate_in_one_with_noise(seed):
    for fen in ("7k/8/5K2/8/8/8/8/6Q1 w - - 0 1", "6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1"):
        state = new_game(fen=fen)
        searcher = Searcher(Genome.reference(), SearchConfig(depth=2, noise=50), random.Random(seed))
        state.push(searcher.choose_move(state))
        assert state.is_checkmate()


def test_noise_only_picks_among_near_best_moves():
    # Brancas podem capturar a dama preta de graça; com ruído de 20 centipeões
    # nenhum outro lance chega perto, então a captura tem de ser escolhida.
    state = new_game(fen="4k3/8/8/3q4/8/8/8/3RK3 w - - 0 1")
    for seed in range(10):
        searcher = Searcher(Genome.reference(), SearchConfig(depth=2, noise=20), random.Random(seed))
        assert state.uci(searcher.choose_move(state)) == "d1d5"


def test_search_prefers_shorter_mate():
    # Dama e rei contra rei: há mate em 1 (Qg7#), a busca em profundidade 3 deve escolhê-lo.
    state = new_game(fen="7k/8/5K2/8/8/8/8/6Q1 w - - 0 1")
    move = Searcher(Genome.reference(), SearchConfig(depth=3)).choose_move(state)
    state.push(move)
    assert state.is_checkmate()


def test_genes_stay_in_bounds():
    rng = random.Random(0)
    g = Genome.random(rng)
    for _ in range(50):
        g = mutate(g, rng, rate=1.0, scale=1.0)
    for name, (lo, hi, _) in GENE_SPECS.items():
        assert lo <= g.genes[name] <= hi


def test_crossover_takes_genes_from_parents():
    rng = random.Random(1)
    a, b = Genome.random(rng, id="a"), Genome.random(rng, id="b")
    child = crossover(a, b, rng, id="c")
    assert child.parents == ("a", "b")
    for n in GENE_SPECS:
        assert child.genes[n] in (a.genes[n], b.genes[n])


def test_fitness_follows_lucas_criterion():
    records = [
        record("rapida", "x", "white", mate_moves=20, wc=5),
        record("lenta", "y", "white", mate_moves=40, wc=0),
        record("rapida_calma", "z", "white", mate_moves=20, wc=1),
        record("sem_mate", "w", None),
    ]
    order = rank(collect_stats(records))
    # Menos lances até o mate primeiro; empate decidido por menos xeques.
    assert order.index("rapida_calma") < order.index("rapida") < order.index("lenta")
    assert order.index("lenta") < order.index("sem_mate")


def test_mate_tiebreak_uses_checks_of_mating_games():
    records = [
        # Mesmo mate em 20; "a" deu mais xeques no total, mas menos na partida do mate.
        record("a", "x", "white", mate_moves=20, wc=1),
        record("y", "a", None, bc=9),
        record("b", "z", "white", mate_moves=20, wc=2),
    ]
    order = rank(collect_stats(records))
    assert order.index("a") < order.index("b")


def test_draw_and_loss_scoring():
    records = [
        # "comeu_dama" empata tendo capturado uma dama: 2,0
        record("comeu_dama", "a", None, wcap={"Q": 1}),
        # "comeu_pecas" empata com torre + bispo + 2 peões: 0,6 + 0,4 + 0,2 = 1,2
        record("comeu_pecas", "b", None, wcap={"R": 1, "B": 1, "P": 2}),
        # "perdeu" capturou uma dama mas levou mate: 2 - 5 = -3
        record("c", "perdeu", "white", mate_moves=30, bcap={"Q": 1}),
    ]
    stats = collect_stats(records)
    assert stats["comeu_dama"].mean_non_win_points == pytest.approx(2.0)
    assert stats["comeu_pecas"].mean_non_win_points == pytest.approx(1.2)
    assert stats["perdeu"].mean_non_win_points == pytest.approx(-3.0)
    order = rank(stats)
    # Quem deu mate continua na frente; depois, mais pontos de empate/derrota.
    assert order[0] == "c"
    assert order.index("comeu_dama") < order.index("comeu_pecas") < order.index("perdeu")
    # No modo puro só os xeques contam entre quem não deu mate (aqui todos zero).
    assert rank(stats, "pure")[0] == "c"


def test_game_records_captures():
    cfg = MatchConfig(search=SearchConfig(depth=1, quiescence_depth=2), max_plies=60)
    r = play_game(Genome.reference(id="a"), Genome.reference(id="b"), cfg, seed=3)
    remaining = {"P": 0, "N": 0, "B": 0, "R": 0, "Q": 0}
    state = new_game()
    for m in r.moves:
        state.push(state.parse_uci(m))
    for _, piece, _ in state.pieces():
        if piece in remaining:
            remaining[piece] += 1
    captured = sum(r.white_captures.values()) + sum(r.black_captures.values())
    assert captured == 30 - sum(remaining.values()) or any(len(m) == 5 for m in r.moves)


def test_schedule_balances_colors():
    pop = [Genome.reference(id=str(i)) for i in range(6)]
    games = schedule(pop, rounds=2, rng=random.Random(0))
    assert len(games) == 12
    for g in pop:
        assert sum(w.id == g.id for w, _ in games) == 2
        assert sum(b.id == g.id for _, b in games) == 2


def test_next_population_keeps_elite():
    cfg = EvolutionConfig(population=6, elite=2)
    ranked = [Genome.random(random.Random(i), id=f"p{i}") for i in range(6)]
    new = next_population(ranked, cfg, generation=2)
    assert len(new) == 6
    assert new[0].genes == ranked[0].genes and new[0].parents == ("p0",)
    assert len({g.id for g in new}) == 6


def test_play_game_is_reproducible():
    cfg = MatchConfig(search=SearchConfig(depth=1, quiescence_depth=0), max_plies=30)
    a, b = Genome.reference(id="a"), Genome.reference(id="b")
    r1 = play_game(a, b, cfg, seed=7)
    r2 = play_game(a, b, cfg, seed=7)
    assert r1.moves == r2.moves
    assert r1.plies <= 30


def test_evolve_saves_and_resumes(tmp_path):
    cfg = EvolutionConfig(
        population=4, elite=1, rounds=1, seed=3,
        match=MatchConfig(search=SearchConfig(depth=1, quiescence_depth=0), max_plies=20),
    )
    run = tmp_path / "run"
    evolve(str(run), 1, cfg, workers=2, log=lambda _: None)
    storage = RunStorage(run)
    assert storage.generation_path(1).exists()
    pgn = storage.pgn_path(1).read_text(encoding="utf-8")
    assert pgn.count("[Event ") == 4
    assert storage.load_state()[0] == 2
    evolve(str(run), 1, workers=1, log=lambda _: None)
    assert [h["generation"] for h in storage.history()] == [1, 2]
    assert storage.load_best() is not None


def test_search_avoids_repetition_with_contempt():
    state = new_game()
    for m in ["g1f3", "g8f6", "f3g1", "f6g8", "g1f3", "g8f6"]:
        state.push(state.parse_uci(m))
    # Voltar com Cg1 repetiria a posição pela terceira vez.
    move = Searcher(Genome.reference(), SearchConfig(depth=2, contempt=200)).choose_move(state)
    state.push(move)
    assert not state.is_repetition()


def test_pgn_export_of_a_mate():
    from luna.pgn import game_to_pgn

    # Mate do louco: 1. f3 e5 2. g4 Qh4#
    rec = record("w", "b", "black", mate_moves=2, termination="checkmate")
    rec.moves = ["f2f3", "e7e5", "g2g4", "d8h4"]
    rec.plies = 4
    pgn = game_to_pgn(rec, event="teste")
    assert '[Result "0-1"]' in pgn
    assert '[White "w"]' in pgn
    assert pgn.rstrip().endswith("1. f3 e5 2. g4 Qh4# 0-1")
