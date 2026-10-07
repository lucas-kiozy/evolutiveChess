"""Resumo curto de um treino da Luna, para conferir antes e depois de treinar.

Uso (da raiz do repositório)::

    python .claude/skills/luna-treino/scripts/resumo_treino.py --run-dir luna/runs/default
    python .claude/skills/luna-treino/scripts/resumo_treino.py --run-dir luna/runs/default --ultimas 5 --estimar 50

Mostra a configuração salva (que vale em toda retomada), as últimas gerações,
os genes do melhor genoma comparados aos de referência e, com ``--estimar N``,
quanto tempo N gerações devem levar pelo ritmo medido até agora.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from luna.genome import GENE_SPECS  # noqa: E402
from luna.storage import RunStorage  # noqa: E402


def fmt(value, digits=1) -> str:
    if value is None:
        return "-"
    return f"{value:.{digits}f}" if isinstance(value, float) else str(value)


def duration(seconds: float) -> str:
    if seconds < 90:
        return f"{seconds:.0f} s"
    if seconds < 5400:
        return f"{seconds / 60:.0f} min"
    return f"{seconds / 3600:.1f} h"


def summarize(run_dir: str, last: int, estimate: int | None) -> dict:
    storage = RunStorage(run_dir)
    if not storage.exists():
        return {"existe": False, "run_dir": run_dir}
    config = storage.load_config()
    history = storage.history()
    next_gen, _ = storage.load_state()
    best = storage.load_best()
    match, search = config["match"], config["match"]["search"]
    out = {
        "existe": True,
        "run_dir": run_dir,
        "proxima_geracao": next_gen,
        "geracoes_concluidas": len(history),
        "config": {
            "populacao": config["population"], "elite": config["elite"], "rodadas": config["rounds"],
            "mutacao": [config["mutation_rate"], config["mutation_scale"]],
            "profundidade": search["depth"], "max_plies": match["max_plies"],
            "backend": match["backend"], "fallback": config["fallback"], "seed": config["seed"],
        },
        "ultimas": history[-last:],
    }
    if best:
        out["melhor"] = {
            "id": best.id,
            "genes": {n: [round(best.genes[n], 2), spec[2]] for n, spec in GENE_SPECS.items()},
        }
    if history:
        recent = history[-min(len(history), 5):]
        per_gen = sum(h["seconds"] for h in recent) / len(recent)
        out["segundos_por_geracao"] = round(per_gen, 2)
        if estimate:
            out["estimativa"] = {"geracoes": estimate, "segundos": round(per_gen * estimate)}
    return out


def print_text(s: dict) -> None:
    if not s["existe"]:
        print(f"Nenhum treino em {s['run_dir']} (o próximo 'train' começa do zero).")
        return
    c = s["config"]
    print(f"Treino {s['run_dir']}: {s['geracoes_concluidas']} gerações concluídas, "
          f"próxima é a {s['proxima_geracao']}")
    print(f"Config salva (vale nas retomadas): população {c['populacao']}, elite {c['elite']}, "
          f"rodadas {c['rodadas']}, mutação {c['mutacao'][0]}/{c['mutacao'][1]}, "
          f"profundidade {c['profundidade']}, max_plies {c['max_plies']}, backend {c['backend']}, "
          f"fallback {c['fallback']}, seed {c['seed']}")
    if s["ultimas"]:
        print("\n| Geração | Partidas | Mates | Mate médio (lances) | Xeques/partida | Melhor | Mate médio do melhor | Tempo |")
        print("|---|---|---|---|---|---|---|---|")
        for h in s["ultimas"]:
            print(f"| {h['generation']} | {h['games']} | {h['mate_rate']:.0%} | {fmt(h['mean_mate_moves'])} | "
                  f"{fmt(h['mean_checks_per_game'], 2)} | {h['best_id']} | {fmt(h['best_mean_mate_moves'])} | "
                  f"{duration(h['seconds'])} |")
    if "melhor" in s:
        print(f"\nMelhor genoma {s['melhor']['id']} (valor atual / referência):")
        print(", ".join(f"{n} {v[0]:g}/{v[1]:g}" for n, v in s["melhor"]["genes"].items()))
    if "segundos_por_geracao" in s:
        print(f"\nRitmo recente: {duration(s['segundos_por_geracao'])} por geração")
    if "estimativa" in s:
        e = s["estimativa"]
        print(f"Estimativa para mais {e['geracoes']} gerações: ~{duration(e['segundos'])}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run-dir", default="luna/runs/default")
    ap.add_argument("--ultimas", type=int, default=10, help="quantas gerações mostrar")
    ap.add_argument("--estimar", type=int, default=None, help="estimar tempo para N gerações")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    s = summarize(args.run_dir, args.ultimas, args.estimar)
    if args.json:
        print(json.dumps(s, ensure_ascii=False, indent=2))
    else:
        print_text(s)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
