"""Catraca de promoção: uma Luna nova só vira a oficial se vencer a oficial atual.

A "melhor" de cada geração é em grande parte a Luna com mais sorte. Na análise de
2026-10-08, as campeãs fizeram 71% dos pontos na geração em que foram escolhidas e
52% na seguinte. Por isso o Lucas decidiu que a troca da Luna oficial depende de um
match direto, como a regra desafiante contra campeão de Pollack e Blair (1998,
Machine Learning 32(3):225-240). Assim o rating oficial nunca cai por sorte.

O match segue o protocolo da seção 8 da análise:

- partidas em pares com a mesma abertura do livro (``luna.openings``) e as cores
  trocadas, para a sorte da abertura se cancelar no par (Glasserman e Yao, 1992);
- profundidade das partidas oficiais (padrão 3) e sem ruído na raiz;
- teste sequencial da razão de verossimilhança de Wald (1945, Annals of
  Mathematical Statistics 16(2):117-186), com H0 = 0 Elo, H1 = +30 Elo e
  alfa = beta = 5%. Ele decide com o menor número médio de partidas; a análise
  estima de 550 a 1.000 partidas;
- teto de 2.000 partidas: se o teste não decidir até lá, a candidata não é promovida.

Sem ruído, cada abertura daria sempre as mesmas duas partidas, e o livro só tem 40.
Por isso, depois do livro vêm ``random_plies`` lances aleatórios, iguais nas duas
partidas do par, o que mantém o pareamento e gera partidas novas.

A razão de verossimilhança usa a aproximação normal sobre o placar médio de cada par
(cinco valores possíveis: 0, 1/4, 1/2, 3/4 e 1). A variância vem dos próprios pares,
então o empate e a correlação entre as duas partidas do par entram na conta. Essa
forma "generalizada" do teste é a usada na prática para testar motores de xadrez
(Fishtest, do Stockfish); ela não tem artigo revisado próprio, mas segue de Wald
com a aproximação normal.
"""

from __future__ import annotations

import math
import random
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass, field
from typing import Callable, Optional

from luna.genome import Genome
from luna.match import MatchConfig, play_game
from luna.openings import BOOK
from luna.search import SearchConfig

OFFICIAL_DEPTH = 3  # profundidade das partidas oficiais (rating e Lichess)
MIN_PAIRS = 8  # pares antes de o teste poder parar (a variância precisa de amostra)


def expected_score(elo: float) -> float:
    """Placar esperado (0 a 1) de quem tem ``elo`` pontos a mais."""
    return 1.0 / (1.0 + 10.0 ** (-elo / 400.0))


@dataclass
class PromotionConfig:
    elo0: float = 0.0  # H0: a candidata não é melhor
    elo1: float = 30.0  # H1: a candidata é 30 Elo melhor
    alpha: float = 0.05  # chance de promover uma candidata que não é melhor
    beta: float = 0.05  # chance de recusar uma candidata 30 Elo melhor
    max_games: int = 2000
    depth: int = OFFICIAL_DEPTH
    random_plies: int = 2  # lances aleatórios depois do livro, iguais no par
    max_plies: int = 200
    backend: str = "chess_engine"
    seed: int = 2026
    batch_pairs: int = 16  # pares jogados por lote antes de olhar o teste

    def __post_init__(self) -> None:
        if self.max_games < 2 * MIN_PAIRS or self.max_games % 2:
            raise ValueError(f"max_games deve ser par e >= {2 * MIN_PAIRS}")
        if not (0 < self.alpha < 1 and 0 < self.beta < 1) or self.elo1 <= self.elo0:
            raise ValueError("use 0 < alpha, beta < 1 e elo1 > elo0")

    @property
    def bounds(self) -> tuple[float, float]:
        """Limites (inferior, superior) da razão de verossimilhança logarítmica."""
        return math.log(self.beta / (1 - self.alpha)), math.log((1 - self.beta) / self.alpha)

    def match_config(self) -> MatchConfig:
        return MatchConfig(
            search=SearchConfig(depth=self.depth, noise=0.0),
            max_plies=self.max_plies,
            random_opening_plies=self.random_plies,
            backend=self.backend,
        )


def llr(pair_scores: list[float], elo0: float, elo1: float) -> float:
    """Razão de verossimilhança logarítmica de H1 contra H0, aproximação normal."""
    n = len(pair_scores)
    if n < 2:
        return 0.0
    mean = sum(pair_scores) / n
    var = sum((x - mean) ** 2 for x in pair_scores) / n
    if var <= 0:
        return 0.0
    s0, s1 = expected_score(elo0), expected_score(elo1)
    return n * (s1 - s0) * (2 * mean - s0 - s1) / (2 * var)


def elo_estimate(pair_scores: list[float]) -> tuple[float, float]:
    """Diferença de Elo estimada e seu erro-padrão (método delta), a partir dos pares."""
    n = len(pair_scores)
    if n == 0:
        return 0.0, float("inf")
    mean = min(max(sum(pair_scores) / n, 1e-3), 1 - 1e-3)
    var = sum((x - mean) ** 2 for x in pair_scores) / max(1, n - 1)
    elo = -400.0 * math.log10(1.0 / mean - 1.0)
    slope = 400.0 / (math.log(10) * mean * (1 - mean))
    return elo, slope * math.sqrt(var / n)


@dataclass
class PromotionResult:
    candidate_id: str
    official_id: str
    promoted: bool
    decision: str  # "H1" (candidata melhor), "H0" (não melhor) ou "teto"
    games: int
    wins: int  # da candidata
    draws: int
    losses: int
    score: float  # placar da candidata, 0 a 1
    elo: float  # candidata menos oficial
    elo_error: float
    llr: float
    bounds: tuple[float, float]
    config: dict = field(default_factory=dict)
    games_detail: list[dict] = field(default_factory=list)

    def to_dict(self, with_games: bool = False) -> dict:
        d = asdict(self)
        if not with_games:
            d.pop("games_detail")
        return d


def _pair_task(args: tuple) -> tuple[float, float, dict, dict]:
    candidate, official, match_config, opening, seed = args
    cand, off = Genome.from_dict(candidate), Genome.from_dict(official)
    first = play_game(cand, off, match_config, seed, opening)
    second = play_game(off, cand, match_config, seed, opening)
    s1 = {"white": 1.0, "black": 0.0, None: 0.5}[first.winner]
    s2 = {"white": 0.0, "black": 1.0, None: 0.5}[second.winner]
    return s1, s2, first.to_dict(), second.to_dict()


def run_promotion_match(
    candidate: Genome,
    official: Genome,
    config: Optional[PromotionConfig] = None,
    workers: int = 0,
    log: Callable[[str], None] = print,
) -> PromotionResult:
    """Joga o match pareado até o teste sequencial decidir ou chegar ao teto.

    Os pares são jogados em lotes em paralelo, mas o teste olha os resultados na
    ordem dos pares, então a decisão não depende do número de processos."""
    config = config or PromotionConfig()
    lower, upper = config.bounds
    match_config = config.match_config()
    max_pairs = config.max_games // 2
    cand_d = {**candidate.to_dict(), "id": candidate.id or "candidata"}
    off_d = {**official.to_dict(), "id": official.id or "oficial"}
    if cand_d["id"] == off_d["id"]:
        off_d["id"] += "-oficial"

    def task(i: int) -> tuple:
        rng = random.Random(f"{config.seed}-pair-{i}")
        return (cand_d, off_d, match_config, BOOK[i % len(BOOK)], rng.randrange(2**32))

    scores: list[float] = []
    pair_scores: list[float] = []
    detail: list[dict] = []
    decision, value = "teto", 0.0
    executor = ProcessPoolExecutor(max_workers=workers or None) if workers != 1 else None
    try:
        next_pair = 0
        while decision == "teto" and next_pair < max_pairs:
            batch = range(next_pair, min(max_pairs, next_pair + config.batch_pairs))
            tasks = [task(i) for i in batch]
            results = list(executor.map(_pair_task, tasks)) if executor else map(_pair_task, tasks)
            for s1, s2, g1, g2 in results:
                scores += [s1, s2]
                pair_scores.append((s1 + s2) / 2)
                detail += [g1, g2]
                value = llr(pair_scores, config.elo0, config.elo1)
                if len(pair_scores) >= MIN_PAIRS and value >= upper:
                    decision = "H1"
                elif len(pair_scores) >= MIN_PAIRS and value <= lower:
                    decision = "H0"
                if decision != "teto":
                    break
            next_pair = batch.stop
            elo, err = elo_estimate(pair_scores)
            log(
                f"{len(scores)} partidas: candidata {sum(scores):g}/{len(scores)}, "
                f"Elo {elo:+.0f} ± {err:.0f}, LLR {value:+.2f} (limites {lower:.2f} e {upper:.2f})"
            )
    finally:
        if executor is not None:
            executor.shutdown()

    elo, err = elo_estimate(pair_scores)
    return PromotionResult(
        candidate_id=cand_d["id"],
        official_id=off_d["id"],
        promoted=decision == "H1",
        decision=decision,
        games=len(scores),
        wins=scores.count(1.0),
        draws=scores.count(0.5),
        losses=scores.count(0.0),
        score=sum(scores) / len(scores) if scores else 0.0,
        elo=elo,
        elo_error=err,
        llr=value,
        bounds=(lower, upper),
        config=asdict(config),
        games_detail=detail,
    )
