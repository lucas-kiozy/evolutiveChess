"""Recomendações da revisão do AG de 2026-11-28, aprovadas pelo Lucas: treino-v5 com
condições congeladas e o que muda na seleção e na variação."""

from luna.evolution import EvolutionConfig, evolve
from luna.match import MatchConfig
from luna.search import SearchConfig
from luna.storage import RunStorage


def _tiny(**kw) -> EvolutionConfig:
    base = dict(
        population=4,
        elite=1,
        games_per_luna=4,
        hall_of_fame=1,
        seed=3,
        boundary_games=0,
        match=MatchConfig(search=SearchConfig(depth=1, quiescence_depth=0), max_plies=20),
    )
    base.update(kw)
    return EvolutionConfig(**base)


# ---------------------------------------------------------- treino congelado


def test_frozen_config_round_trips_without_migrations():
    cfg = EvolutionConfig()
    d = cfg.to_dict()
    assert d["frozen"] is True
    back = EvolutionConfig.from_dict(d)
    assert back == cfg
    # Sem migrações: a escala desligada e a falta de limite de tempo ficam como estão.
    d["match"]["search"].update(schedule=None, time_limit=None, quiescence_depth=4)
    search = EvolutionConfig.from_dict(d).match.search
    assert search.schedule is None and search.time_limit is None
    assert search.quiescence_depth == 4


def test_new_run_saves_code_tag_and_config_in_every_generation(tmp_path):
    run = tmp_path / "treino-x"
    evolve(str(run), 1, _tiny(), workers=1, log=lambda _: None)
    storage = RunStorage(run)
    saved = storage.load_config()
    assert saved["frozen"] is True and saved["run_tag"] == "treino-x" and "code" in saved
    gen1 = storage.load_generation(1)
    assert gen1["config"]["run_tag"] == "treino-x" and "code" in gen1
    assert all(p["id"].startswith("treino-x-g0001-") for p in gen1["population"])
    # Retomar não muda a configuração congelada.
    evolve(str(run), 1, workers=1, log=lambda _: None)
    gen2 = storage.load_generation(2)
    assert gen2["config"] == gen1["config"]
    assert all(p["id"].startswith("treino-x-g0002-") for p in gen2["population"])
