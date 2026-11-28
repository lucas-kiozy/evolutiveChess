"""Simulação da elite "sem ruído congelado" antes de mudar o treino (revisão do AG de
2026-11-28, aprovada pelo Lucas com a condição de testar por simulação antes).

Um AG sintético com a mesma seleção da Luna: população de 20, elite de 2 com os
resultados acumulados, torneio de 3, ordem pelo Bradley–Terry do próprio
``luna.ranking`` com a mesma priori. Cada Luna tem uma força verdadeira em Elo; a filha
herda a média dos pais mais uma mutação gaussiana; as partidas são sorteadas pela
fórmula do Elo, em pares com cores trocadas. Compara três modos da elite:

- ``atual``: a elite leva todas as partidas, inclusive as da geração em que foi
  escolhida (o "ruído congelado": ela continua sendo ordenada pela sorte que a elegeu);
- ``fresca``: a elite que acabou de entrar não leva as partidas da audição; quem
  continua na elite acumula só as partidas jogadas depois de entrar;
- ``fresca+5``: como ``fresca``, e um genoma sai da elite depois de 5 gerações seguidas.

Mede a resposta à seleção (Elo verdadeiro médio da população por geração), a fração
de cópias da elite que seguem no top-2 e a correlação da ordem com a força verdadeira.

Uso::

    python tools/simular_elite.py --geracoes 25 --repeticoes 24 --mutacao 10
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from luna.ranking import bradley_terry, results_of  # noqa: E402

MODES = ("atual", "fresca", "fresca+5")


def _score(rng: random.Random, a: float, b: float, draw: float) -> float:
    """Placar de a contra b, com empates na fração ``draw``."""
    p = 1.0 / (1.0 + 10 ** ((b - a) / 400.0))
    if rng.random() < draw:
        return 0.5
    return 1.0 if rng.random() < p else 0.0


def run(
    mode: str,
    seed: int,
    generations: int = 25,
    population: int = 20,
    elite: int = 2,
    games: int = 18,
    mutation: float = 10.0,
    prior_games: float = 12.0,
    draw: float = 0.12,
    tenure_max: int = 5,
) -> dict:
    rng = random.Random(seed)
    strength = {f"g1-{i}": rng.gauss(0.0, mutation) for i in range(population)}
    ids = list(strength)
    carry: dict[str, dict] = {}  # id -> {"results": [...], "tenure": n}
    means, kept, corrs = [], [], []
    next_id = 0
    for gen in range(1, generations + 1):
        results = []
        for _ in range(games // 2):
            order = ids[:]
            rng.shuffle(order)
            for a, b in zip(order[0::2], order[1::2]):
                for w, k in ((a, b), (b, a)):
                    results.append((w, k, _score(rng, strength[w], strength[k], draw)))
        used = list(results)
        for i, c in carry.items():
            used += [(i, opp, s) for opp, s in c["results"]]
        bt = bradley_terry(used, prior_games)
        ranked = sorted(ids, key=lambda i: (-bt[i].elo, i))
        means.append(statistics.fmean(strength[i] for i in ids))
        corrs.append(_spearman([bt[i].elo for i in ids], [strength[i] for i in ids]))
        copies = [i for i in ids if i in carry]
        kept += [ranked.index(i) < elite for i in copies]
        retired = set()
        if mode == "fresca+5":
            retired = {i for i, c in carry.items() if c["tenure"] >= tenure_max}
        elites = [i for i in ranked if i not in retired][:elite]
        new_ids, new_strength, new_carry = [], {}, {}
        for p in elites:
            next_id += 1
            child = f"g{gen + 1}-{next_id}"
            new_ids.append(child)
            new_strength[child] = strength[p]
            prev = carry.get(p)
            if mode == "atual" or prev is not None:
                new_carry[child] = {
                    "results": results_of(p, used),
                    "tenure": (prev["tenure"] + 1) if prev else 1,
                }
            else:  # acabou de entrar: as partidas da audição ficam de fora
                new_carry[child] = {"results": [], "tenure": 1}
        while len(new_ids) < population:
            a = ranked[min(rng.randrange(population) for _ in range(3))]
            b = ranked[min(rng.randrange(population) for _ in range(3))]
            next_id += 1
            child = f"g{gen + 1}-{next_id}"
            new_ids.append(child)
            new_strength[child] = (strength[a] + strength[b]) / 2 + rng.gauss(0.0, mutation)
        ids, strength, carry = new_ids, new_strength, new_carry
    slope = _slope(means)
    return {
        "resposta": slope,
        "elite_no_top2": statistics.fmean(kept) if kept else math.nan,
        "spearman": statistics.fmean(corrs),
    }


def _slope(ys: list[float]) -> float:
    xs = range(len(ys))
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return num / sum((x - mx) ** 2 for x in xs)


def _spearman(a: list[float], b: list[float]) -> float:
    def ranks(v: list[float]) -> list[int]:
        order = sorted(range(len(v)), key=v.__getitem__)
        r = [0] * len(v)
        for pos, i in enumerate(order):
            r[i] = pos
        return r

    ra, rb = ranks(a), ranks(b)
    n = len(a)
    d2 = sum((x - y) ** 2 for x, y in zip(ra, rb))
    return 1 - 6 * d2 / (n * (n * n - 1))


def summarize(rows: list[dict]) -> dict:
    out = {}
    for key in rows[0]:
        vals = [r[key] for r in rows]
        out[key] = [statistics.fmean(vals), statistics.stdev(vals) / math.sqrt(len(vals))]
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--geracoes", type=int, default=25)
    ap.add_argument("--repeticoes", type=int, default=24)
    ap.add_argument("--mutacao", type=float, nargs="+", default=[10.0, 20.0])
    ap.add_argument("--saida", help="arquivo JSON com o resultado")
    args = ap.parse_args(argv)
    report = {}
    for mut in args.mutacao:
        for mode in MODES:
            rows = [run(mode, seed, args.geracoes, mutation=mut) for seed in range(args.repeticoes)]
            s = summarize(rows)
            report[f"mutacao={mut:g} {mode}"] = s
            print(
                f"mutação {mut:>4g} Elo  {mode:<9} resposta {s['resposta'][0]:+.2f} ± "
                f"{s['resposta'][1]:.2f} Elo/geração  elite segue no top-2 "
                f"{s['elite_no_top2'][0]:.0%}  Spearman {s['spearman'][0]:.2f}"
            )
    if args.saida:
        Path(args.saida).write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
