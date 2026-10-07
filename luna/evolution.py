"""Laço evolutivo: partidas em paralelo, seleção, cruzamento e mutação."""

from __future__ import annotations

import datetime
import random
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass, field
from typing import Callable, Optional

from luna.fitness import FALLBACKS, collect_stats, rank
from luna.genome import Genome, crossover, mutate
from luna.match import GameRecord, MatchConfig, play_game
from luna.pgn import games_to_pgn
from luna.search import SearchConfig
from luna.storage import RunStorage


@dataclass
class EvolutionConfig:
    population: int = 16
    elite: int = 2  # melhores copiados intactos para a próxima geração
    tournament_size: int = 3
    mutation_rate: float = 0.2  # chance de cada gene mutar
    mutation_scale: float = 0.05  # desvio da mutação, fração da faixa do gene
    rounds: int = 2  # rodadas por geração; cada rodada = 2 partidas por Luna (cores trocadas)
    workers: int = 0  # 0 = número de CPUs
    seed: int = 42
    fallback: str = "captures"  # pontuação de empates e derrotas; ver fitness.py
    match: MatchConfig = field(default_factory=MatchConfig)

    def __post_init__(self) -> None:
        if self.population < 2 or self.population % 2:
            raise ValueError("population deve ser par e >= 2")
        if not 0 <= self.elite < self.population:
            raise ValueError("elite deve estar entre 0 e population - 1")
        if self.fallback not in FALLBACKS:
            raise ValueError(f"fallback deve ser um de {FALLBACKS}")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "EvolutionConfig":
        d = dict(d)
        m = dict(d.pop("match", {}))
        m["search"] = SearchConfig(**m.get("search", {}))
        return cls(match=MatchConfig(**m), **d)


def _play_task(args: tuple) -> GameRecord:
    white, black, match_config, seed = args
    return play_game(Genome.from_dict(white), Genome.from_dict(black), match_config, seed)


def schedule(population: list[Genome], rounds: int, rng: random.Random) -> list[tuple[Genome, Genome]]:
    """Em cada rodada, embaralha e emparelha; cada par joga duas partidas com cores trocadas."""
    pairs = []
    for _ in range(rounds):
        order = population[:]
        rng.shuffle(order)
        for a, b in zip(order[0::2], order[1::2]):
            pairs.append((a, b))
            pairs.append((b, a))
    return pairs


def play_generation(
    population: list[Genome],
    config: EvolutionConfig,
    generation: int,
    executor: Optional[ProcessPoolExecutor] = None,
) -> list[GameRecord]:
    rng = random.Random(f"{config.seed}-schedule-{generation}")
    games = schedule(population, config.rounds, rng)
    tasks = [
        (w.to_dict(), b.to_dict(), config.match, rng.randrange(2**32))
        for w, b in games
    ]
    if executor is None:
        return [_play_task(t) for t in tasks]
    return list(executor.map(_play_task, tasks))


def tournament_select(ranked: list[Genome], size: int, rng: random.Random) -> Genome:
    """Torneio: sorteia ``size`` indivíduos e fica com o de melhor posição."""
    picks = [rng.randrange(len(ranked)) for _ in range(size)]
    return ranked[min(picks)]


def next_population(ranked: list[Genome], config: EvolutionConfig, generation: int) -> list[Genome]:
    rng = random.Random(f"{config.seed}-breed-{generation}")
    new: list[Genome] = []
    for i, g in enumerate(ranked[: config.elite]):
        new.append(Genome(dict(g.genes), id=_ident(generation, i), parents=(g.id,)))
    while len(new) < config.population:
        a = tournament_select(ranked, config.tournament_size, rng)
        b = tournament_select(ranked, config.tournament_size, rng)
        child = crossover(a, b, rng, id=_ident(generation, len(new)))
        child = mutate(child, rng, config.mutation_rate, config.mutation_scale)
        new.append(child)
    return new


def initial_population(config: EvolutionConfig) -> list[Genome]:
    rng = random.Random(f"{config.seed}-init")
    pop = [Genome.reference(id=_ident(1, 0))]
    while len(pop) < config.population:
        pop.append(Genome.random(rng, id=_ident(1, len(pop))))
    return pop


def _ident(generation: int, index: int) -> str:
    return f"g{generation:04d}-i{index:02d}"


def summarize(generation: int, ranked_ids: list[str], stats: dict, records: list[GameRecord], seconds: float) -> dict:
    mates = [r for r in records if r.termination == "checkmate"]
    terminations: dict[str, int] = {}
    for r in records:
        terminations[r.termination] = terminations.get(r.termination, 0) + 1
    best = stats[ranked_ids[0]]
    return {
        "generation": generation,
        "games": len(records),
        "mate_rate": len(mates) / len(records) if records else 0.0,
        "mean_mate_moves": (sum(r.mate_moves for r in mates) / len(mates)) if mates else None,
        "mean_checks_per_game": sum(r.white_checks + r.black_checks for r in records) / max(1, len(records)),
        "terminations": terminations,
        "best_id": ranked_ids[0],
        "best_mean_mate_moves": best.mean_mate_moves,
        "best_checks_per_game": best.checks_per_game,
        "seconds": round(seconds, 2),
    }


def evolve(
    run_dir: str,
    generations: int,
    config: Optional[EvolutionConfig] = None,
    workers: Optional[int] = None,
    log: Callable[[str], None] = print,
) -> list[dict]:
    """Roda ``generations`` gerações. Se ``run_dir`` já tiver um treino, retoma de onde parou
    (a configuração salva prevalece sobre ``config``)."""
    storage = RunStorage(run_dir)
    if storage.exists():
        config = EvolutionConfig.from_dict(storage.load_config())
        start, population = storage.load_state()
        log(f"Retomando {run_dir} na geração {start}")
    else:
        config = config or EvolutionConfig()
        storage.save_config(config.to_dict())
        start, population = 1, initial_population(config)
        storage.save_state(start, population)
        log(f"Novo treino em {run_dir}")

    n_workers = workers if workers is not None else config.workers
    summaries = []
    executor = ProcessPoolExecutor(max_workers=n_workers or None) if n_workers != 1 else None
    try:
        for generation in range(start, start + generations):
            t0 = time.perf_counter()
            records = play_generation(population, config, generation, executor)
            stats = collect_stats(records)
            ranked_ids = rank(stats, config.fallback)
            by_id = {g.id: g for g in population}
            ranked = [by_id[i] for i in ranked_ids]
            summary = summarize(generation, ranked_ids, stats, records, time.perf_counter() - t0)
            storage.save_generation(
                generation,
                {
                    "generation": generation,
                    "summary": summary,
                    "population": [
                        {**by_id[i].to_dict(), "rank": r + 1, "stats": stats[i].to_dict()}
                        for r, i in enumerate(ranked_ids)
                    ],
                    "games": [rec.to_dict() for rec in records],
                },
            )
            storage.save_pgn(
                generation,
                games_to_pgn(
                    records,
                    event=f"Luna geração {generation}",
                    date=datetime.date.today().strftime("%Y.%m.%d"),
                    backend=config.match.backend,
                ),
            )
            population = next_population(ranked, config, generation + 1)
            storage.save_state(generation + 1, population)
            summaries.append(summary)
            log(
                f"Geração {generation}: {summary['games']} partidas, "
                f"mates {summary['mate_rate']:.0%}, melhor {summary['best_id']} "
                f"(mate médio {summary['best_mean_mate_moves']}, "
                f"xeques/partida {summary['best_checks_per_game']:.2f}) em {summary['seconds']}s"
            )
    finally:
        if executor is not None:
            executor.shutdown()
    return summaries
