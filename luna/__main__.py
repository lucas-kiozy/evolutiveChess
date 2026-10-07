"""Linha de comando da Luna.

Exemplos::

    python -m luna train --run-dir luna/runs/default --generations 10 --population 16
    python -m luna train --run-dir luna/runs/default --generations 10   # retoma
    python -m luna show --run-dir luna/runs/default
    python -m luna export --run-dir luna/runs/default --name luna-v1   # salva a melhor como versão
    python -m luna versions                                            # lista as versões salvas
"""

from __future__ import annotations

import argparse
import json

from luna.evolution import EvolutionConfig, evolve
from luna.match import MatchConfig
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
    t.add_argument("--rounds", type=int, default=2)
    t.add_argument("--mutation-rate", type=float, default=0.2)
    t.add_argument("--mutation-scale", type=float, default=0.05)
    t.add_argument("--depth", type=int, default=2)
    t.add_argument("--quiescence-depth", type=int, default=4)
    t.add_argument("--noise", type=float, default=5.0)
    t.add_argument("--contempt", type=float, default=50.0)
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

    args = parser.parse_args(argv)
    if args.command == "export":
        from luna.versions import export_version

        path = export_version(
            args.run_dir, args.name, args.generation, args.notes, overwrite=args.overwrite
        )
        print(f"Versão salva em {path}")
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
            rounds=args.rounds,
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


if __name__ == "__main__":
    main()
