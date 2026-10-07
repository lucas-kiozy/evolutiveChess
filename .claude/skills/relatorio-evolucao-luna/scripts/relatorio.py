"""Relatório de evolução da Luna: a IA está melhorando de geração em geração?

Uso (da raiz do repositório)::

    python .claude/skills/relatorio-evolucao-luna/scripts/relatorio.py --run-dir luna/runs/default
    python .claude/skills/relatorio-evolucao-luna/scripts/relatorio.py --run-dir luna/runs/default \
        --elo --checkpoints 5 --partidas 20 --grafico evolucao.png --saida relatorio.md

Sem ``--elo`` o relatório só lê o histórico salvo (instantâneo). As métricas do
histórico são de self-play dentro de cada geração, então dizem como a
população joga entre si, não se ela ficou mais forte. ``--elo`` responde isso:
o melhor genoma de algumas gerações (checkpoints) joga contra o melhor da
primeira geração (âncora, Elo 0) e o Elo relativo é estimado por máxima
verossimilhança (rating/elo.py).
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from luna.evolution import EvolutionConfig  # noqa: E402
from luna.genome import GENE_SPECS, Genome  # noqa: E402
from luna.match import play_game  # noqa: E402
from luna.storage import RunStorage  # noqa: E402


def mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def trend(history: list[dict]) -> dict:
    """Compara o primeiro e o último terço do treino."""
    n = len(history)
    k = max(1, n // 3)
    early, late = history[:k], history[-k:]
    block = lambda rows: {  # noqa: E731
        "geracoes": [rows[0]["generation"], rows[-1]["generation"]],
        "taxa_mate": mean([r["mate_rate"] for r in rows]),
        "mate_medio": mean([r["mean_mate_moves"] for r in rows]),
        "xeques_partida": mean([r["mean_checks_per_game"] for r in rows]),
    }
    a, b = block(early), block(late)
    signs = []
    if a["taxa_mate"] is not None and b["taxa_mate"] is not None:
        signs.append((b["taxa_mate"] - a["taxa_mate"]) / 0.05)  # 5 pontos percentuais = 1 unidade
    if a["mate_medio"] is not None and b["mate_medio"] is not None:
        signs.append((a["mate_medio"] - b["mate_medio"]) / 3.0)  # 3 lances a menos = 1 unidade
    score = sum(signs) / len(signs) if signs else 0.0
    verdict = "melhorando" if score >= 1 else "piorando" if score <= -1 else "estável"
    return {"inicio": a, "fim": b, "veredito": verdict, "poucos_dados": n < 10}


def sample(history: list[dict], max_rows: int) -> list[dict]:
    if len(history) <= max_rows:
        return history
    step = (len(history) - 1) / (max_rows - 1)
    idx = sorted({round(i * step) for i in range(max_rows)})
    return [history[i] for i in idx]


def best_of(storage: RunStorage, generation: int) -> Genome:
    return Genome.from_dict(storage.load_generation(generation)["population"][0])


def _game(args):
    challenger, anchor, match, seed, challenger_white = args
    white, black = (challenger, anchor) if challenger_white else (anchor, challenger)
    rec = play_game(Genome.from_dict(white), Genome.from_dict(black), match, seed)
    if rec.winner is None:
        return 0.5, rec.termination
    won = (rec.winner == "white") == challenger_white
    return (1.0 if won else 0.0), rec.termination


def relative_elo(storage: RunStorage, history: list[dict], checkpoints: int, games: int,
                 workers: int, anchor_kind: str = "geracao1") -> list[dict]:
    from rating.elo import GameResult, estimate_rating

    config = EvolutionConfig.from_dict(storage.load_config())
    gens = [h["generation"] for h in history]
    picks = {gens[round(i * (len(gens) - 1) / max(1, checkpoints - 1))] for i in range(checkpoints)}
    if anchor_kind == "referencia":
        anchor = Genome.reference().to_dict()
        picks = sorted(picks)
    else:
        anchor = best_of(storage, gens[0]).to_dict()
        picks = sorted(picks - {gens[0]})
    tasks, owners = [], []
    for g in picks:
        challenger = best_of(storage, g).to_dict()
        for i in range(games):
            tasks.append((challenger, anchor, config.match, 10_000 * g + i, i % 2 == 0))
            owners.append(g)
    with ProcessPoolExecutor(max_workers=workers or None) as pool:
        outcomes = list(pool.map(_game, tasks))
    rows = [] if anchor_kind == "referencia" else [
        {"geracao": gens[0], "elo": 0.0, "erro": 0.0, "partidas": 0, "pontos": None, "ancora": True}]
    for g in picks:
        scores = [s for (s, _), o in zip(outcomes, owners) if o == g]
        est = estimate_rating([GameResult(0.0, s) for s in scores], prior_mean=0.0, prior_sd=700.0)
        rows.append({"geracao": g, "elo": round(est.rating), "erro": round(est.stderr),
                     "partidas": len(scores), "pontos": est.score, "ancora": False})
    return rows


def gene_drift(storage: RunStorage, history: list[dict]) -> list[tuple[str, float, float, float]]:
    first = best_of(storage, history[0]["generation"]).genes
    last = best_of(storage, history[-1]["generation"]).genes
    rows = []
    for name, (lo, hi, _) in GENE_SPECS.items():
        rows.append((name, first[name], last[name], (last[name] - first[name]) / (hi - lo)))
    return sorted(rows, key=lambda r: -abs(r[3]))


def fmt(v, d=1):
    return "-" if v is None else f"{v:.{d}f}"


def render(run_dir, history, tr, elo, drift, max_rows, anchor_kind="geracao1") -> str:
    anchor_text = ("o genoma de referência, com os pesos iniciais" if anchor_kind == "referencia"
                   else "a primeira geração")
    out = [f"# Evolução da Luna ({run_dir})", ""]
    out.append(f"{len(history)} gerações, da {history[0]['generation']} à {history[-1]['generation']}.")
    out.append("")
    out.append(f"**Tendência no self-play: {tr['veredito']}.** "
               f"Taxa de mate {fmt(100 * tr['inicio']['taxa_mate'], 0)}% → {fmt(100 * tr['fim']['taxa_mate'], 0)}%, "
               f"mate médio {fmt(tr['inicio']['mate_medio'])} → {fmt(tr['fim']['mate_medio'])} lances "
               f"(gerações {tr['inicio']['geracoes'][0]}-{tr['inicio']['geracoes'][1]} contra "
               f"{tr['fim']['geracoes'][0]}-{tr['fim']['geracoes'][1]}).")
    if tr["poucos_dados"]:
        out.append("")
        out.append("Poucas gerações para tirar conclusão; trate a tendência como provisória.")
    if elo:
        out += ["", f"## Elo relativo (melhor de cada checkpoint contra {anchor_text}, Elo 0)", "",
                "| Geração | Elo relativo | ± erro-padrão | Partidas | Pontos |", "|---|---|---|---|---|"]
        for r in elo:
            if r["ancora"]:
                out.append(f"| {r['geracao']} | 0 (âncora) | - | - | - |")
            else:
                out.append(f"| {r['geracao']} | {r['elo']:+d} | {r['erro']} | {r['partidas']} | {r['pontos']:g} |")
        last = elo[-1]
        if not last["ancora"]:
            low = last["elo"] - 1.96 * last["erro"]
            if low > 0:
                verdict = f"mais forte que {anchor_text}, com 95% de confiança"
            elif last["elo"] + 1.96 * last["erro"] < 0:
                verdict = f"mais fraca que {anchor_text}, com 95% de confiança"
            else:
                verdict = f"sem diferença comprovada contra {anchor_text}; jogue mais partidas para afinar"
            out += ["", f"Última geração medida: {verdict}."]
        out += ["", "Elo relativo ao próprio treino, não comparável ao Lichess/FIDE; para isso use `python -m rating`."]
    out += ["", "## Por geração", "",
            "| Geração | Partidas | Mates | Mate médio | Xeques/partida | Fins de partida |", "|---|---|---|---|---|---|"]
    for h in sample(history, max_rows):
        ends = ", ".join(f"{k} {v}" for k, v in sorted(h["terminations"].items(), key=lambda kv: -kv[1]))
        out.append(f"| {h['generation']} | {h['games']} | {h['mate_rate']:.0%} | {fmt(h['mean_mate_moves'])} | "
                   f"{fmt(h['mean_checks_per_game'], 2)} | {ends} |")
    if len(history) > max_rows:
        out += ["", f"(amostra de {max_rows} gerações, incluindo a primeira e a última)"]
    out += ["", "## Genes que mais mudaram (melhor da 1ª geração → melhor da última)", "",
            "| Gene | Antes | Depois | Variação (% da faixa) |", "|---|---|---|---|"]
    for name, a, b, rel in drift[:6]:
        out.append(f"| {name} | {a:.1f} | {b:.1f} | {100 * rel:+.0f}% |")
    return "\n".join(out) + "\n"


def plot(history, elo, path):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return "matplotlib não instalado; gráfico não gerado (pip install matplotlib)"
    gens = [h["generation"] for h in history]
    panels = 3 if elo else 2
    fig, axes = plt.subplots(panels, 1, figsize=(8, 2.6 * panels), sharex=True)
    axes[0].plot(gens, [100 * h["mate_rate"] for h in history], "o-", color="#2a6f97", markersize=3)
    axes[0].set_ylabel("Partidas com mate (%)")
    mates = [(h["generation"], h["mean_mate_moves"]) for h in history if h["mean_mate_moves"] is not None]
    axes[1].plot([g for g, _ in mates], [m for _, m in mates], "o-", color="#c46d1d", markersize=3)
    axes[1].set_ylabel("Lances até o mate")
    if elo:
        axes[2].errorbar([r["geracao"] for r in elo], [r["elo"] for r in elo],
                         yerr=[1.96 * r["erro"] for r in elo], fmt="o-", color="#3c7a3c", capsize=3)
        axes[2].axhline(0, color="#999", linewidth=0.8)
        axes[2].set_ylabel("Elo relativo (IC 95%)")
    for ax in axes:
        ax.grid(alpha=0.3)
    axes[-1].set_xlabel("Geração")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run-dir", default="luna/runs/default")
    ap.add_argument("--elo", action="store_true", help="mede Elo relativo jogando partidas")
    ap.add_argument("--checkpoints", type=int, default=4, help="gerações medidas, incluindo a primeira e a última")
    ap.add_argument("--ancora", choices=["geracao1", "referencia"], default="geracao1",
                    help="adversário fixo: melhor da 1ª geração ou genoma de referência")
    ap.add_argument("--partidas", type=int, default=20, help="partidas por checkpoint (pares = cores equilibradas)")
    ap.add_argument("--workers", type=int, default=0, help="0 = número de CPUs")
    ap.add_argument("--max-linhas", type=int, default=30)
    ap.add_argument("--grafico", type=Path, default=None, help="salva um PNG")
    ap.add_argument("--saida", type=Path, default=None, help="salva o relatório em Markdown")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    storage = RunStorage(args.run_dir)
    history = storage.history()
    if not history:
        print(f"Nenhuma geração concluída em {args.run_dir}.")
        return 1
    tr = trend(history)
    elo = (relative_elo(storage, history, args.checkpoints, args.partidas, args.workers, args.ancora)
           if args.elo and len(history) > 1 else None)
    drift = gene_drift(storage, history)
    text = render(args.run_dir, history, tr, elo, drift, args.max_linhas, args.ancora)
    if args.saida:
        args.saida.write_text(text, encoding="utf-8")
    if args.json:
        print(json.dumps({"tendencia": tr, "elo": elo,
                          "genes": [dict(zip(("gene", "antes", "depois", "variacao"), d)) for d in drift]},
                         ensure_ascii=False, indent=2))
    else:
        print(text, end="")
    if args.grafico:
        warn = plot(history, elo, args.grafico)
        print(warn or f"Gráfico salvo em {args.grafico}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
