"""Linha de comando da Luna.

Exemplos::

    python -m luna train --run-dir luna/runs/default --generations 10 --population 16
    python -m luna train --run-dir luna/runs/default --generations 10   # retoma
    python -m luna show --run-dir luna/runs/default
    python -m luna export --run-dir luna/runs/default --name luna-v1   # salva a melhor como versão
    python -m luna versions                                            # lista as versões salvas
    python -m luna promote --run-dir luna/runs/default --name luna-v3  # catraca de promoção
"""

from __future__ import annotations

import argparse
import json

from luna.evolution import EvolutionConfig, evolve
from luna.genome import Genome
from luna.match import MatchConfig
from luna.promotion import OFFICIAL_DEPTH
from luna.search import SearchConfig
from luna.storage import RunStorage


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="luna", description="Luna: IA de xadrez evolutiva")
    sub = parser.add_subparsers(dest="command", required=True)

    t = sub.add_parser("train", help="treina (ou retoma) uma população")
    t.add_argument("--run-dir", default="luna/runs/default")
    t.add_argument("--generations", type=int, default=10)
    t.add_argument("--population", type=int, default=16)
    t.add_argument("--elite", type=int, default=2)
    t.add_argument("--games-per-luna", type=int, default=18)
    t.add_argument("--hall-of-fame", type=int, default=2, help="campeãs passadas por Luna")
    t.add_argument("--mutation-rate", type=float, default=0.2)
    t.add_argument("--mutation-scale", type=float, default=0.05)
    t.add_argument("--depth", type=int, default=2)
    t.add_argument("--quiescence-depth", type=int, help="fixa a quiescência (padrão: gene)")
    t.add_argument("--noise", type=float, default=5.0)
    t.add_argument("--contempt", type=float, help="fixa o contempt (padrão: gene)")
    t.add_argument("--max-plies", type=int, default=200)
    t.add_argument("--opening-plies", type=int, default=2)
    t.add_argument("--backend", choices=["chess_engine", "python-chess"], default="chess_engine")
    t.add_argument("--workers", type=int, default=0, help="0 = número de CPUs")
    t.add_argument("--seed", type=int, default=42)

    s = sub.add_parser("show", help="mostra o histórico e o melhor genoma")
    s.add_argument("--run-dir", default="luna/runs/default")

    e = sub.add_parser("export", help="salva a melhor Luna de uma geração como versão nomeada")
    e.add_argument("--run-dir", default="luna/runs/default")
    e.add_argument("--name", help="padrão: luna-gNNNN")
    e.add_argument("--generation", type=int, help="padrão: a última avaliada")
    e.add_argument("--notes", default="")
    e.add_argument("--overwrite", action="store_true")

    sub.add_parser("versions", help="lista as versões salvas em luna/versions/")

    p = sub.add_parser(
        "promote", help="match da candidata contra a Luna oficial; ela só vira oficial se vencer"
    )
    p.add_argument("--candidate", help="versão candidata (nome ou caminho)")
    p.add_argument("--run-dir", help="ou: a melhor Luna de uma geração deste treino")
    p.add_argument("--generation", type=int, help="padrão: a última avaliada")
    p.add_argument("--name", help="nome da versão nova, quando a candidata vem de um treino")
    p.add_argument("--notes", default="")
    p.add_argument("--official", help="padrão: a de luna/versions/oficial.txt")
    p.add_argument("--depth", type=int, default=OFFICIAL_DEPTH)
    p.add_argument("--elo1", type=float, default=30.0, help="H1 do teste sequencial, em Elo")
    p.add_argument("--max-games", type=int, default=2000)
    p.add_argument("--random-plies", type=int, default=2, help="lances aleatórios após o livro")
    p.add_argument("--workers", type=int, default=0, help="0 = número de CPUs")
    p.add_argument("--seed", type=int, default=2026)
    p.add_argument("--report", help="JSON com o resultado e as partidas do match")

    args = parser.parse_args(argv)
    if args.command == "export":
        from luna.versions import export_version

        path = export_version(
            args.run_dir, args.name, args.generation, args.notes, overwrite=args.overwrite
        )
        print(f"Versão salva em {path}")
        return
    if args.command == "promote":
        _promote(args)
        return
    if args.command == "versions":
        from luna.versions import list_versions

        for v in list_versions():
            src = v.source
            print(
                f"{v.name}: geração {src.get('generation')} de {src.get('run_dir')} ({v.created})"
            )
        return
    if args.command == "train":
        config = EvolutionConfig(
            population=args.population,
            elite=args.elite,
            games_per_luna=args.games_per_luna,
            hall_of_fame=args.hall_of_fame,
            mutation_rate=args.mutation_rate,
            mutation_scale=args.mutation_scale,
            workers=args.workers,
            seed=args.seed,
            match=MatchConfig(
                search=SearchConfig(
                    depth=args.depth,
                    quiescence_depth=args.quiescence_depth,
                    noise=args.noise,
                    contempt=args.contempt,
                ),
                max_plies=args.max_plies,
                random_opening_plies=args.opening_plies,
                backend=args.backend,
            ),
        )
        evolve(args.run_dir, args.generations, config, workers=args.workers)
    else:
        storage = RunStorage(args.run_dir)
        for row in storage.history():
            print(json.dumps(row, ensure_ascii=False))
        best = storage.load_best()
        if best:
            print("Melhor genoma:", json.dumps(best.to_dict(), ensure_ascii=False, indent=2))


def _promote(args: argparse.Namespace) -> None:
    from luna import versions as v
    from luna.promotion import PromotionConfig, run_promotion_match

    official = v.load_version(args.official or v.official_name())
    if bool(args.candidate) == bool(args.run_dir):
        raise SystemExit("Use --candidate ou --run-dir (um dos dois).")
    if args.candidate:
        candidate = v.load_version(args.candidate)
    else:
        if not args.name:
            raise SystemExit("Com --run-dir, dê o nome da versão nova em --name.")
        if v.version_path(args.name).exists():
            raise SystemExit(f"A versão {args.name} já existe.")
        candidate = v.version_from_run(args.run_dir, args.name, args.generation, args.notes)
    config = PromotionConfig(
        elo1=args.elo1,
        max_games=args.max_games,
        depth=args.depth,
        random_plies=args.random_plies,
        seed=args.seed,
    )
    print(f"Candidata {candidate.name} contra a oficial {official.name}, profundidade {args.depth}")
    cand_genome = Genome(dict(candidate.genome.genes), id=candidate.name)
    off_genome = Genome(dict(official.genome.genes), id=official.name)
    result = run_promotion_match(cand_genome, off_genome, config, workers=args.workers)
    summary = result.to_dict()
    if args.report:
        with open(args.report, "w", encoding="utf-8") as fh:
            json.dump(result.to_dict(with_games=True), fh, ensure_ascii=False, indent=1)
    if not result.promoted:
        print(
            f"Não promovida ({result.decision}): {result.score:.1%} em {result.games} partidas, "
            f"Elo {result.elo:+.0f} ± {result.elo_error:.0f}. A oficial continua {official.name}."
        )
        return
    if args.run_dir:
        candidate.source["promotion"] = summary
        v.save_version(candidate)
    v.set_official(candidate.name)
    print(
        f"Promovida: {candidate.name} fez {result.score:.1%} em {result.games} partidas "
        f"(Elo {result.elo:+.0f} ± {result.elo_error:.0f}) e agora é a Luna oficial."
    )


if __name__ == "__main__":
    main()
