"""Compara a velocidade dos backends de xadrez da Luna.

Uso, a partir da raiz do repositório:
    python tools/bench_backends.py --partidas 20 --profundidade 2 --semente 2026

Para cada backend registrado em ``luna.adapters.BACKENDS`` roda as mesmas
partidas Luna x Luna (mesmos genomas e mesma semente) e imprime uma tabela.
Divergências entre backends são listadas, mas o código de saída é 0, a menos
que se passe ``--estrito`` (aí sai com 1 se houver divergência).
"""

from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path

# Rodando como `python tools/bench_backends.py`, o sys.path[0] é `tools/`;
# acrescenta a raiz do repositório para importar `luna` sem instalação.
_RAIZ = str(Path(__file__).resolve().parents[1])
if _RAIZ not in sys.path:
    sys.path.insert(0, _RAIZ)

from luna.adapters import BACKENDS  # noqa: E402
from luna.genome import Genome  # noqa: E402
from luna.match import MatchConfig, play_game  # noqa: E402
from luna.search import SearchConfig  # noqa: E402


def gerar_pares(partidas: int, semente: int) -> list[tuple[Genome, Genome]]:
    rng = random.Random(semente)
    return [
        (Genome.random(rng, id=f"b{i}-w"), Genome.random(rng, id=f"b{i}-p"))
        for i in range(partidas)
    ]


def rodar_backend(nome: str, pares, profundidade: int, max_lances: int, semente: int):
    cfg = MatchConfig(
        search=SearchConfig(depth=profundidade, quiescence_depth=2),
        max_plies=max_lances,
        backend=nome,
    )
    registros = []
    inicio = time.perf_counter()
    for i, (branco, preto) in enumerate(pares):
        registros.append(play_game(branco, preto, cfg, seed=semente + i).to_dict())
    segundos = time.perf_counter() - inicio
    return registros, segundos


def formatar_tabela(linhas: list[tuple], coincidem: bool) -> str:
    cab = ("backend", "partidas", "meios-lances", "segundos", "meios-lances/s")
    corpo = [
        (n, str(p), str(m), f"{s:.2f}", f"{m / s:.1f}" if s > 0 else "inf") for n, p, m, s in linhas
    ]
    larg = [max(len(r[i]) for r in [cab, *corpo]) for i in range(len(cab))]
    fmt = "  ".join(f"{{:<{w}}}" for w in larg)
    saida = [fmt.format(*cab), fmt.format(*("-" * w for w in larg))]
    saida += [fmt.format(*r) for r in corpo]
    saida.append(f"resultados coincidem entre backends: {'sim' if coincidem else 'NÃO'}")
    return "\n".join(saida)


def partidas_divergentes(todos: list[list[dict]]) -> list[tuple[int, int]]:
    """(índice da partida, primeiro meio-lance diferente) em relação ao primeiro backend."""
    saida = []
    for i, ref in enumerate(todos[0]):
        for outro in todos[1:]:
            if outro[i] != ref:
                a, b = ref["moves"], outro[i]["moves"]
                ply = next((k for k, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
                saida.append((i, ply))
                break
    return saida


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--partidas", type=int, default=20)
    ap.add_argument("--profundidade", type=int, default=2)
    ap.add_argument("--semente", type=int, default=2026)
    ap.add_argument(
        "--max-lances", type=int, default=200, help="limite de meios-lances por partida"
    )
    ap.add_argument(
        "--estrito", action="store_true", help="sai com código 1 se os resultados divergirem"
    )
    args = ap.parse_args(argv)

    pares = gerar_pares(args.partidas, args.semente)
    linhas, resultados = [], {}
    for nome in BACKENDS:
        registros, segundos = rodar_backend(
            nome, pares, args.profundidade, args.max_lances, args.semente
        )
        resultados[nome] = registros
        total = sum(r["plies"] for r in registros)
        linhas.append((nome, len(registros), total, segundos))
    todos = list(resultados.values())
    divergentes = partidas_divergentes(todos)
    print(formatar_tabela(linhas, not divergentes))
    if divergentes:
        print(
            "ATENÇÃO: partidas divergentes entre backends (índice: primeiro meio-lance diferente):"
        )
        for i, ply in divergentes:
            print(f"  partida {i}: meio-lance {ply}")
    return 1 if (divergentes and args.estrito) else 0


if __name__ == "__main__":
    sys.exit(main())
