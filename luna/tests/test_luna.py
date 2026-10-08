import random

import pytest

from luna.adapters import new_game
from luna.evaluation import evaluate
from luna.evolution import EvolutionConfig, evolve, next_population, schedule
from luna.fitness import collect_stats, rank
from luna.game_interface import GameState
from luna.genome import GENE_SPECS, Genome, crossover, mutate
from luna.match import GameRecord, MatchConfig, play_game
from luna.search import SearchConfig, Searcher
from luna.storage import RunStorage


def record(
    white, black, winner, mate_moves=None, wc=0, bc=0, termination=None, wcap=None, bcap=None
):
    return GameRecord(
        white_id=white,
        black_id=black,
        winner=winner,
        termination=termination or ("checkmate" if mate_moves else "max_plies"),
        plies=0,
        white_checks=wc,
        black_checks=bc,
        mate_moves=mate_moves,
        material_balance=0,
        moves=[],
        white_captures=wcap or {},
        black_captures=bcap or {},
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
        searcher = Searcher(
            Genome.reference(), SearchConfig(depth=2, noise=50), random.Random(seed)
        )
        state.push(searcher.choose_move(state))
        assert state.is_checkmate()


def test_noise_only_picks_among_near_best_moves():
    # Brancas podem capturar a dama preta de graça; com ruído de 20 centipeões
    # nenhum outro lance chega perto, então a captura tem de ser escolhida.
    state = new_game(fen="4k3/8/8/3q4/8/8/8/3RK3 w - - 0 1")
    for seed in range(10):
        searcher = Searcher(
            Genome.reference(), SearchConfig(depth=2, noise=20), random.Random(seed)
        )
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


def test_result_scale_decides_first():
    records = [
        # "vence_perde": 5 - 1 = 4; "dois_empates": 2 + 2 = 4; "vence_tudo": 10
        record("vence_perde", "x", "white", mate_moves=30),
        record("y", "vence_perde", "white", mate_moves=30),
        record("dois_empates", "z", None, wcap={"Q": 1}),
        record("w", "dois_empates", None),
        record("vence_tudo", "a", "white", mate_moves=40, wc=9),
        record("b", "vence_tudo", "black", mate_moves=40, bc=9),
    ]
    stats = collect_stats(records)
    assert stats["vence_perde"].result_points == 4
    assert stats["dois_empates"].result_points == 4
    assert stats["vence_tudo"].result_points == 10
    # Só as três jogaram 2 partidas cada; as adversárias jogaram 1.
    order = rank({i: stats[i] for i in ("vence_perde", "dois_empates", "vence_tudo")})
    assert order[0] == "vence_tudo"
    # Mesma soma na régua: desempata pelos pontos de captura (dama = 2).
    assert order.index("dois_empates") < order.index("vence_perde")


def test_win_always_beats_draw_with_many_captures():
    everything = {"P": 8, "N": 2, "B": 2, "R": 2, "Q": 1}
    records = [
        record("venceu", "x", "white", mate_moves=60, wc=30),
        record("empatou", "y", None, wcap=everything),
    ]
    assert rank(collect_stats(records))[0] == "venceu"


def test_captures_count_in_losses():
    records = [record("c", "perdeu", "white", mate_moves=30, bcap={"Q": 1, "P": 2})]
    s = collect_stats(records)["perdeu"]
    assert s.result_points == -1
    assert s.capture_points == pytest.approx(2.2)


def test_wins_tiebreak_fewer_checks_then_fewer_moves():
    records = [
        record("objetiva", "x", "white", mate_moves=40, wc=1),
        record("rapida", "y", "white", mate_moves=20, wc=6),
        record("rapida_calma", "z", "white", mate_moves=20, wc=1),
    ]
    order = [i for i in rank(collect_stats(records)) if i in ("objetiva", "rapida", "rapida_calma")]
    # Menos xeques primeiro; com xeques iguais, menos lances até o mate.
    assert order == ["rapida_calma", "objetiva", "rapida"]


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
    games = schedule(pop, 2, random.Random(0))
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
        population=4,
        elite=1,
        games_per_luna=4,
        hall_of_fame=1,
        seed=3,
        boundary_games=0,
        match=MatchConfig(search=SearchConfig(depth=1, quiescence_depth=0), max_plies=20),
    )
    run = tmp_path / "run"
    evolve(str(run), 1, cfg, workers=2, log=lambda _: None)
    storage = RunStorage(run)
    assert storage.generation_path(1).exists()
    pgn = storage.pgn_path(1).read_text(encoding="utf-8")
    # Geração 1 ainda não tem campeãs: 4 Lunas x 4 partidas / 2 = 8 partidas entre si.
    assert pgn.count("[Event ") == 8
    assert storage.load_state()[0] == 2
    hall, carry = storage.load_hall_of_fame()
    assert len(hall) == 1 and len(carry) == 1
    evolve(str(run), 1, workers=1, log=lambda _: None)
    assert [h["generation"] for h in storage.history()] == [1, 2]
    assert storage.load_best() is not None
    gen2 = storage.load_generation(2)
    # Cada Luna jogou 4 partidas na geração 2, 2 delas contra a campeã da geração 1.
    for luna in gen2["population"]:
        played = [g for g in gen2["games"] if luna["id"] in (g["white_id"], g["black_id"])]
        assert len(played) == 4
        assert sum("campea-" in g["white_id"] + g["black_id"] for g in played) == 2
    # A elite leva as 4 partidas da geração 1 e soma as 4 da geração 2.
    elite = next(p for p in gen2["population"] if p["id"] == "g0002-i00")
    assert elite["stats"]["games"] == 8


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


def test_export_and_load_version(tmp_path):
    from luna.versions import export_version, list_versions, load_version

    cfg = EvolutionConfig(
        population=4,
        elite=1,
        games_per_luna=2,
        hall_of_fame=0,
        seed=5,
        match=MatchConfig(search=SearchConfig(depth=1, quiescence_depth=0, noise=3), max_plies=20),
    )
    run = tmp_path / "run"
    evolve(str(run), 2, cfg, workers=1, log=lambda _: None)
    vdir = tmp_path / "versions"
    path = export_version(run, name="luna-teste", notes="primeira", versions_dir=vdir)
    v = load_version("luna-teste", versions_dir=vdir)
    best = RunStorage(run).load_generation(2)["population"][0]
    assert path.name == "luna-teste.json"
    assert v.genome.genes == best["genes"]
    assert v.search == SearchConfig(depth=1, quiescence_depth=0, noise=3)
    assert v.source["generation"] == 2 and v.notes == "primeira"
    assert [x.name for x in list_versions(vdir)] == ["luna-teste"]
    with pytest.raises(FileExistsError):
        export_version(run, name="luna-teste", versions_dir=vdir)
    # Versão de uma geração específica e com nome padrão
    assert export_version(run, generation=1, versions_dir=vdir).name == "luna-g0001.json"


def test_each_luna_plays_18_games_with_hall_of_fame():
    from luna.evolution import play_generation

    cfg = EvolutionConfig(
        population=4,
        match=MatchConfig(search=SearchConfig(depth=1, quiescence_depth=0), max_plies=4),
    )
    pop = [Genome.reference(id=f"l{i}") for i in range(4)]
    hall = [Genome.reference(id=f"c{i}") for i in range(3)]
    records = play_generation(pop, cfg, 1, hall_of_fame=hall)
    for luna in pop:
        played = [r for r in records if luna.id in (r.white_id, r.black_id)]
        vs_champions = [r for r in played if "campea-" in r.white_id + r.black_id]
        assert len(played) == 18
        assert len(vs_champions) == 4
        assert sum(r.white_id == luna.id for r in played) == 9


def test_old_config_with_rounds_still_loads():
    cfg = EvolutionConfig(population=4).to_dict()
    del cfg["games_per_luna"], cfg["hall_of_fame"]
    cfg["rounds"], cfg["fallback"] = 2, "captures"
    old = EvolutionConfig.from_dict(cfg)
    assert old.games_per_luna == 4 and old.hall_of_fame == 0


def test_ranking_uses_average_per_game():
    from luna.fitness import Stats

    veteran = Stats(games=8, wins=4, draws=4)  # média 3,5
    newcomer = Stats(games=4, wins=3, draws=1)  # média 4,25
    assert rank({"veterana": veteran, "novata": newcomer}) == ["novata", "veterana"]
