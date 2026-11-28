"""Confronto controlado de um gene e sensibilidade à profundidade (revisão do AG de
2026-11-28, aprovada pelo Lucas).

Clones idênticos de um genoma-base, que só diferem no gene escolhido, jogam pares
contra o clone de controle (o primeiro valor de ``--valores``): mesma abertura do
livro e mesmos lances aleatórios nas duas partidas do par, cores trocadas. Como os
outros genes são iguais, a diferença de Elo é o efeito do gene naquele fundo genético,
sem a confusão do parentesco que existe nos dados do treino.

Com ``--condicoes treino oficial`` o mesmo confronto roda nas duas buscas (treino:
escala 2/3/4/5, limite de nós, ruído 5; oficial: escala 2/4/5, orçamento de 20 s, sem
ruído). A diferença entre os dois efeitos mede se o valor bom no treino continua bom
nas partidas oficiais (interação genótipo x ambiente).

Tamanho: com a dispersão de pares da catraca da g45 (0,266 por par), 343 pares dão erro
de ~10 Elo e 536 pares, ~8 Elo. Cada confronto é retomável: rode de novo o mesmo
comando depois de um reinício.

Rodar só quando a máquina estiver livre (são horas de partidas). Exemplo::

    python tools/confronto_genes.py --base luna/versions/luna-v5.json \\
        --gene check_extension --valores 1 2 3 --condicoes treino --pares 343 \\
        --out /caminho/confronto-check-extension
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from luna import promotion  # noqa: E402
from luna.evolution import TRAINING_SEARCH  # noqa: E402
from luna.genome import GENE_SPECS, Genome  # noqa: E402
from luna.match import MatchConfig  # noqa: E402
from luna.versions import load_version  # noqa: E402

CONDITIONS = ("treino", "oficial")


@dataclass
class GeneMatchConfig(promotion.PromotionConfig):
    """Pares de tamanho fixo na busca do treino ou na oficial."""

    condition: str = "treino"

    def match_config(self) -> MatchConfig:
        if self.condition == "oficial":
            return super().match_config()
        return MatchConfig(
            search=TRAINING_SEARCH,
            max_plies=self.max_plies,
            random_opening_plies=self.random_plies,
            backend=self.backend,
        )


def variant(base: Genome, gene: str, value: float, name: str) -> Genome:
    return Genome({**base.genes, gene: value}, id=f"{name}-{gene}={value:g}")


def run(args: argparse.Namespace, log=print) -> dict:
    if args.gene not in GENE_SPECS:
        raise SystemExit(f"gene desconhecido: {args.gene}")
    base_v = load_version(args.base)
    base = base_v.genome
    control_value, *others = args.valores
    if not others:
        raise SystemExit("dê pelo menos dois valores: o de controle e um para comparar")
    out = Path(args.out)
    report: dict = {"base": base_v.name, "gene": args.gene, "controle": control_value}
    for condition in args.condicoes:
        control = variant(base, args.gene, control_value, base_v.name)
        for value in others:
            test = variant(base, args.gene, value, base_v.name)
            key = f"{condition} {args.gene}={value:g} x {control_value:g}"
            cfg = GeneMatchConfig(
                condition=condition,
                sequential=False,
                max_games=2 * args.pares,
                out_dir=str(out / f"{condition}-{value:g}-x-{control_value:g}"),
                seed=f"genes-{args.gene}-{base_v.name}",  # mesmos pares em todos os valores
            )
            if condition == "oficial":
                cfg = replace(cfg, time_limit=promotion.OFFICIAL_MOVE_TIME)
            log(f"{key}: {args.pares} pares")
            result = promotion.run_promotion_match(test, control, cfg, args.workers, log)
            report[key] = {
                "elo": result.elo,
                "elo_error": result.elo_error,
                "games": result.games,
                "score": result.score,
            }
    for value in others:
        keys = [f"{c} {args.gene}={value:g} x {control_value:g}" for c in CONDITIONS]
        if all(k in report for k in keys):
            t, o = (report[k] for k in keys)
            report[f"interacao {args.gene}={value:g}"] = {
                "oficial_menos_treino": o["elo"] - t["elo"],
                "erro": (o["elo_error"] ** 2 + t["elo_error"] ** 2) ** 0.5,
            }
    out.mkdir(parents=True, exist_ok=True)
    (out / "resumo.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", required=True, help="versão da Luna (nome ou caminho)")
    ap.add_argument("--gene", required=True)
    ap.add_argument("--valores", type=float, nargs="+", required=True)
    ap.add_argument("--condicoes", nargs="+", choices=CONDITIONS, default=["treino"])
    ap.add_argument("--pares", type=int, default=343)
    ap.add_argument("--workers", type=int, default=0, help="0 = número de CPUs")
    ap.add_argument("--out", required=True)
    report = run(ap.parse_args(argv))
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
