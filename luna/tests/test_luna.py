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


def record(white, black, winner, mate_moves=None, wc=0, bc=0, termination=None):
    return GameRecord(
        white_id=white, black_id=black, winner=winner,
        termination=termination or ("checkmate" if mate_moves else "max_plies"),
        plies=0, white_checks=wc, black_checks=bc, mate_moves=mate_moves,
        material_balance=0, moves=[],
    )


def test_adapter_implements_interface():
    state = new_game()
    assert isinstance(state, GameState)
    assert len(state.legal_moves()) == 20
    state.push("e2e4")
    assert not state.white_to_move and state.ply == 1
    assert state.pop() == "e2e4"


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
    assert move == "a1a8"


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


def test_points_fallback_only_affects_non_mating():
    records = [
        record("mate", "a", "white", mate_moves=30, wc=9),
        record("ganhou_no_tempo", "b", "white", wc=3, termination="max_plies"),
        record("empatou_calmo", "c", None, wc=0),
    ]
    stats = collect_stats(records)
    pure = rank(stats, "pure")
    points = rank(stats, "points")
    assert pure[0] == points[0] == "mate"
    assert pure.index("empatou_calmo") < pure.index("ganhou_no_tempo")
    assert points.index("ganhou_no_tempo") < points.index("empatou_calmo")


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
    assert storage.load_state()[0] == 2
    evolve(str(run), 1, workers=1, log=lambda _: None)
    assert [h["generation"] for h in storage.history()] == [1, 2]
    assert storage.load_best() is not None


def test_search_avoids_repetition_with_contempt():
    state = new_game()
    for m in ["g1f3", "g8f6", "f3g1", "f6g8", "g1f3", "g8f6"]:
        state.push(m)
    # Voltar com Cg1 repetiria a posição pela terceira vez.
    move = Searcher(Genome.reference(), SearchConfig(depth=2, contempt=200)).choose_move(state)
    state.push(move)
    assert not state.is_repetition()
