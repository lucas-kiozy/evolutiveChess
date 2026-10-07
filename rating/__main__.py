"""Linha de comando: ``python -m rating --player modulo:fabrica``.

Exemplo (jogador aleatório, só para testar a instalação)::

    python -m rating --player rating.player:random_player_factory --games 8 --movetime 0.05
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rating.estimator import EstimatorConfig, RatingEstimator
from rating.player import load_factory
from rating.stockfish_opponent import TimeControl


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m rating", description=__doc__.splitlines()[0])
    ap.add_argument("--player", required=True, help="fábrica do jogador, 'modulo:funcao'")
    ap.add_argument("--target", type=float, default=1600)
    ap.add_argument("--games", type=int, default=60, help="máximo de partidas")
    ap.add_argument("--parallel", type=int, default=4, help="partidas simultâneas")
    ap.add_argument("--stderr", type=float, default=40, help="para quando o erro-padrão chegar aqui")
    ap.add_argument("--start-elo", type=int, default=1320)
    ap.add_argument("--tc", default="60+0.6", help="relógio do Stockfish, base+incremento (s)")
    ap.add_argument("--movetime", type=float, default=None, help="segundos fixos por lance (mais rápido, menos fiel à calibração)")
    ap.add_argument("--stockfish", default=None, help="caminho do executável")
    ap.add_argument("--history", type=Path, default=Path("rating/runs/history.jsonl"))
    ap.add_argument("--json", action="store_true", help="imprime o resultado final em JSON")
    args = ap.parse_args(argv)

    cfg = EstimatorConfig(
        target=args.target,
        max_games=args.games,
        batch_size=max(1, args.parallel),
        stderr_target=args.stderr,
        start_elo=args.start_elo,
        time_control=TimeControl.parse(args.tc),
        movetime=args.movetime,
        stockfish_path=args.stockfish,
        history_file=args.history,
    )

    def progress(rep):
        print(rep.summary(), end="\n\n", file=sys.stderr, flush=True)

    report = RatingEstimator(load_factory(args.player), cfg, progress=progress).run()
    print(json.dumps(report.to_dict(), indent=2) if args.json else report.summary())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
