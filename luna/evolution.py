"""Laço evolutivo: partidas em paralelo, seleção, cruzamento e mutação.

Para reduzir o ruído da aptidão (poucas partidas fazem a ordem das Lunas sair quase
por sorteio), três medidas aprovadas pelo Lucas, seguindo a literatura sobre
algoritmos genéticos com avaliação ruidosa:

- cada Luna joga ``games_per_luna`` partidas por geração (padrão 18);
- a elite carrega os resultados das gerações anteriores, então sua pontuação é a
  média de mais partidas (média ao longo do tempo; Jin e Branke, 2005);
- parte das partidas é contra campeãs de gerações passadas, o "hall of fame" de
  Rosin e Belew (1997), que dá adversárias fixas e mostra se há progresso.

Depois da análise de 2026-10-08, o Lucas decidiu ordenar as Lunas pela força
estimada com Bradley–Terry (``luna.ranking``), e não mais pela soma da régua. Quando
a última vaga da elite fica separada da seguinte por menos que o erro das duas, elas
jogam ``boundary_games`` partidas extras pareadas antes de fechar a elite: é a ideia
das corridas, que gastam partidas onde a decisão está em jogo (Maron e Moore, 1997,
Artificial Intelligence Review 11:193-225).

Referências: Y. Jin, J. Branke, "Evolutionary optimization in uncertain
environments: a survey", IEEE Trans. Evolutionary Computation 9(3):303-317, 2005.
C. D. Rosin, R. K. Belew, "New methods for competitive coevolution", Evolutionary
Computation 5(1):1-29, 1997.
"""

from __future__ import annotations

import datetime
import math
import random
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass, field
from typing import Callable, Optional

from luna.fitness import Stats, collect_stats, rank, sort_key
from luna.genome import Genome, crossover, mutate
from luna.match import GameRecord, MatchConfig, play_game
from luna.openings import BOOK
from luna.pgn import games_to_pgn
from luna.ranking import Strength, bradley_terry, game_results, results_of
from luna.search import SearchConfig
from luna.storage import RunStorage

#: Busca padrão do treino: profundidade 2, e 3 do lance 5 ao 12 (decisão do Lucas).
TRAINING_SEARCH = SearchConfig(depth=2, noise=5.0, deep_depth=3, deep_from_move=5, deep_to_move=12)
RANKINGS = ("bradley_terry", "regua")


@dataclass
class EvolutionConfig:
    population: int = 16
    elite: int = 2  # melhores copiados intactos para a próxima geração
    tournament_size: int = 3
    mutation_rate: float = 0.2  # chance de cada gene mutar
    mutation_scale: float = 0.05  # desvio da mutação, fração da faixa do gene
    games_per_luna: int = 18  # partidas de cada Luna por geração (par: cores trocadas)
    hall_of_fame: int = 2  # campeãs passadas que cada Luna enfrenta (2 partidas cada)
    workers: int = 0  # 0 = número de CPUs
    seed: int = 42
    ranking: str = "bradley_terry"  # ou "regua": soma da régua com os desempates
    boundary_games: int = 8  # partidas extras na fronteira da elite (par; 0 desliga)
    prior_games: float = 12.0  # partidas virtuais contra a média (Bradley–Terry)
    match: MatchConfig = field(default_factory=lambda: MatchConfig(search=TRAINING_SEARCH))

    def __post_init__(self) -> None:
        if self.population < 2 or self.population % 2:
            raise ValueError("population deve ser par e >= 2")
        if not 0 <= self.elite < self.population:
            raise ValueError("elite deve estar entre 0 e population - 1")
        if self.games_per_luna < 2 or self.games_per_luna % 2:
            raise ValueError("games_per_luna deve ser par e >= 2")
        if not 0 <= 2 * self.hall_of_fame <= self.games_per_luna:
            raise ValueError("hall_of_fame deve caber em games_per_luna (2 partidas cada)")
        if self.ranking not in RANKINGS:
            raise ValueError(f"ranking deve ser um de {RANKINGS}")
        if self.boundary_games < 0 or self.boundary_games % 2:
            raise ValueError("boundary_games deve ser par e >= 0")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "EvolutionConfig":
        d = dict(d)
        d.pop("fallback", None)  # opção antiga, substituída pela régua 5/2/-1
        if "rounds" in d:  # treinos antigos: 2 partidas por rodada e sem hall of fame
            d["games_per_luna"] = 2 * d.pop("rounds")
            d.setdefault("hall_of_fame", 0)
        m = dict(d.pop("match", {}))
        search = dict(m.get("search", {}))
        # Treinos antigos gravavam a quiescência e o contempt fixos da busca (sempre os
        # padrões 4 e 50). Hoje são genes; com os padrões fora, eles evoluem também
        # nesses treinos, partindo dos mesmos valores (luna.genome.LEGACY_DEFAULTS).
        for key, legacy in (("quiescence_depth", 4), ("contempt", 50.0)):
            if search.get(key) == legacy:
                search.pop(key)
        # Treinos de antes da janela funda passam a usá-la também, como o Lucas pediu.
        for key in ("deep_depth", "deep_from_move", "deep_to_move"):
            search.setdefault(key, getattr(TRAINING_SEARCH, key))
        m["search"] = SearchConfig.from_dict(search)
        return cls(match=MatchConfig(**m), **d)


def _play_task(args: tuple) -> GameRecord:
    white, black, match_config, seed, *opening = args
    return play_game(Genome.from_dict(white), Genome.from_dict(black), match_config, seed, *opening)


def schedule(
    population: list[Genome], rounds: int, rng: random.Random
) -> list[tuple[Genome, Genome]]:
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
    hall_of_fame: Optional[list[Genome]] = None,
) -> list[GameRecord]:
    """Joga as partidas da geração: cada Luna faz ``games_per_luna`` partidas, das quais
    2 contra cada uma de ``hall_of_fame`` campeãs sorteadas e o resto entre si."""
    rng = random.Random(f"{config.seed}-schedule-{generation}")
    hall = hall_of_fame or []
    k = min(config.hall_of_fame, len(hall))
    games = schedule(population, (config.games_per_luna - 2 * k) // 2, rng)
    for luna in population:
        for champion in rng.sample(hall, k):
            opponent = Genome(dict(champion.genes), id=f"campea-{champion.id}")
            games.append((luna, opponent))
            games.append((opponent, luna))
    tasks = [(w.to_dict(), b.to_dict(), config.match, rng.randrange(2**32)) for w, b in games]
    if executor is None:
        return [_play_task(t) for t in tasks]
    return list(executor.map(_play_task, tasks))


def play_boundary(
    a: Genome,
    b: Genome,
    config: EvolutionConfig,
    generation: int,
    executor: Optional[ProcessPoolExecutor] = None,
) -> list[GameRecord]:
    """Partidas extras entre ``a`` e ``b``: pares com a mesma abertura do livro e os
    mesmos lances aleatórios, cores trocadas."""
    rng = random.Random(f"{config.seed}-fronteira-{generation}")
    tasks = []
    for _ in range(config.boundary_games // 2):
        opening, seed = BOOK[rng.randrange(len(BOOK))], rng.randrange(2**32)
        tasks.append((a.to_dict(), b.to_dict(), config.match, seed, opening))
        tasks.append((b.to_dict(), a.to_dict(), config.match, seed, opening))
    if executor is None:
        return [_play_task(t) for t in tasks]
    return list(executor.map(_play_task, tasks))


@dataclass
class GenerationRanking:
    ids: list[str]  # do melhor para o pior
    stats: dict[str, Stats]
    strengths: dict[str, Strength]  # vazio na ordenação pela régua
    results: list[tuple[str, str, float]]  # partidas usadas, com as acumuladas da elite
    records: list[GameRecord]  # partidas da geração, com as extras da fronteira
    boundary: Optional[tuple[str, str]] = None  # quem jogou as partidas extras


def rank_generation(
    population: list[Genome],
    records: list[GameRecord],
    carry: dict,
    config: EvolutionConfig,
    generation: int,
    executor: Optional[ProcessPoolExecutor] = None,
) -> GenerationRanking:
    by_id = {g.id: g for g in population}

    def build(records: list[GameRecord]) -> GenerationRanking:
        all_stats = collect_stats(records)
        stats = {i: all_stats.get(i, Stats()) for i in by_id}  # sem as campeãs
        results = game_results(records)
        for ident, previous in carry.items():
            if ident in stats:
                stats[ident].merge(Stats.from_dict(previous))
                results += [(ident, opp, s) for opp, s in previous.get("results", [])]
        if config.ranking == "regua":
            return GenerationRanking(rank(stats), stats, {}, results, records)
        strengths = bradley_terry(results, config.prior_games)
        ids = sorted(by_id, key=lambda i: (-round(strengths[i].elo, 9), sort_key(stats[i]), i))
        return GenerationRanking(ids, stats, strengths, results, records)

    ranking = build(records)
    elite = config.elite
    if ranking.strengths and config.boundary_games and 0 < elite < len(population):
        a, b = ranking.ids[elite - 1], ranking.ids[elite]
        sa, sb = ranking.strengths[a], ranking.strengths[b]
        if sa.elo - sb.elo < math.hypot(sa.error, sb.error):
            extra = play_boundary(by_id[a], by_id[b], config, generation, executor)
            ranking = build(records + extra)
            ranking.boundary = (a, b)
    return ranking


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


def summarize(
    generation: int,
    ranked_ids: list[str],
    stats: dict,
    records: list[GameRecord],
    seconds: float,
    strengths: Optional[dict] = None,
) -> dict:
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
        "mean_checks_per_game": sum(r.white_checks + r.black_checks for r in records)
        / max(1, len(records)),
        "terminations": terminations,
        "best_id": ranked_ids[0],
        "best_result_points": best.result_points,
        "best_record": [best.wins, best.draws, best.losses],
        "best_mean_win_checks": best.mean_win_checks,
        "best_mean_mate_moves": best.mean_mate_moves,
        "best_checks_per_game": best.checks_per_game,
        "best_games": best.games,
        "best_elo": strengths[ranked_ids[0]].elo if strengths else None,
        "best_elo_error": strengths[ranked_ids[0]].error if strengths else None,
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
        hall, carry = storage.load_hall_of_fame()
        log(f"Retomando {run_dir} na geração {start}")
    else:
        config = config or EvolutionConfig()
        storage.save_config(config.to_dict())
        start, population = 1, initial_population(config)
        hall, carry = [], {}
        storage.save_state(start, population)
        log(f"Novo treino em {run_dir}")

    n_workers = workers if workers is not None else config.workers
    summaries = []
    executor = ProcessPoolExecutor(max_workers=n_workers or None) if n_workers != 1 else None
    try:
        for generation in range(start, start + generations):
            t0 = time.perf_counter()
            records = play_generation(population, config, generation, executor, hall)
            by_id = {g.id: g for g in population}
            ranking = rank_generation(population, records, carry, config, generation, executor)
            records, stats, ranked_ids = ranking.records, ranking.stats, ranking.ids
            strengths = ranking.strengths
            ranked = [by_id[i] for i in ranked_ids]
            summary = summarize(
                generation, ranked_ids, stats, records, time.perf_counter() - t0, strengths
            )
            summary["boundary"] = list(ranking.boundary) if ranking.boundary else None
            storage.save_generation(
                generation,
                {
                    "generation": generation,
                    "summary": summary,
                    "population": [
                        {
                            **by_id[i].to_dict(),
                            "rank": r + 1,
                            "stats": stats[i].to_dict(),
                            "strength": asdict(strengths[i]) if strengths else None,
                        }
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
            champion = ranked[0]
            if all(champion.genes != h.genes for h in hall):
                hall.append(Genome(dict(champion.genes), id=champion.id))
            population = next_population(ranked, config, generation + 1)
            # A elite (primeiras da nova população) leva os resultados acumulados, com a
            # lista de partidas para o Bradley–Terry da geração seguinte.
            carry = {
                g.id: {
                    **stats[g.parents[0]].to_dict(),
                    "results": results_of(g.parents[0], ranking.results),
                }
                for g in population[: config.elite]
            }
            storage.save_state(generation + 1, population, hall, carry)
            summaries.append(summary)
            log(
                f"Geração {generation}: {summary['games']} partidas, "
                f"mates {summary['mate_rate']:.0%}, melhor {summary['best_id']} "
                f"(força {_fmt_elo(summary)}, "
                f"{summary['best_result_points']:g} pontos em {summary['best_games']} partidas, "
                f"V/E/D {summary['best_record']}, "
                f"xeques por vitória {summary['best_mean_win_checks']}, "
                f"mate médio {summary['best_mean_mate_moves']}), "
                f"{len(hall)} campeãs, em {summary['seconds']}s"
            )
    finally:
        if executor is not None:
            executor.shutdown()
    return summaries


def _fmt_elo(summary: dict) -> str:
    if summary.get("best_elo") is None:
        return "pela régua"
    return f"{summary['best_elo']:+.0f} ± {summary['best_elo_error']:.0f}"
