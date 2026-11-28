"""Ferramentas da revisão do AG de 2026-11-28: confronto de genes e simulação da elite."""

import importlib.util
import random
import sys
from pathlib import Path

from luna import promotion

_TOOLS = Path(__file__).resolve().parents[1]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, _TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses procuram o módulo em sys.modules
    spec.loader.exec_module(module)
    return module


def test_gene_match_compares_clones_in_both_conditions(tmp_path, monkeypatch):
    seen = []

    def fake(args):
        cand, off, match_config, _, seed = args
        seen.append((cand["genes"]["check_extension"], off["genes"]["check_extension"]))
        assert {k: v for k, v in cand["genes"].items() if k != "check_extension"} == {
            k: v for k, v in off["genes"].items() if k != "check_extension"
        }
        rng = random.Random(seed)
        return float(rng.random() < 0.6), float(rng.random() < 0.6), {}, {}

    monkeypatch.setattr(promotion, "_pair_task", fake)
    tool = _load("confronto_genes")
    report = tool.run(
        tool.argparse.Namespace(
            base="luna-v5",
            gene="check_extension",
            valores=[1.0, 2.0],
            condicoes=["treino", "oficial"],
            pares=16,
            workers=1,
            out=str(tmp_path),
        ),
        log=lambda _: None,
    )
    assert set(seen) == {(2.0, 1.0)}
    assert "interacao check_extension=2" in report
    assert (tmp_path / "resumo.json").exists()


def test_elite_simulation_runs():
    tool = _load("simular_elite")
    for mode in tool.MODES:
        row = tool.run(mode, seed=1, generations=4, mutation=10.0)
        assert set(row) == {"resposta", "elite_no_top2", "spearman"}
