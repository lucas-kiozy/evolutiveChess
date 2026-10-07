"""Persistência do treino: configuração, gerações, histórico e estado para retomar.

Layout de ``run_dir``::

    config.json               configuração do treino
    state.json                próxima geração e população a avaliar (retomada)
    history.jsonl             um resumo por geração
    best_genome.json          melhor genoma da última geração avaliada
    generations/gen_0001.json população avaliada, estatísticas e partidas
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

from luna.genome import Genome


def _write_json(path: Path, data: Any) -> None:
    """Escreve de forma atômica para não corromper o arquivo se o treino cair."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _read_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class RunStorage:
    def __init__(self, run_dir: str | Path):
        self.root = Path(run_dir)

    @property
    def config_path(self) -> Path:
        return self.root / "config.json"

    @property
    def state_path(self) -> Path:
        return self.root / "state.json"

    def generation_path(self, generation: int) -> Path:
        return self.root / "generations" / f"gen_{generation:04d}.json"

    def exists(self) -> bool:
        return self.state_path.exists()

    def save_config(self, config: dict) -> None:
        _write_json(self.config_path, config)

    def load_config(self) -> dict:
        return _read_json(self.config_path)

    def save_generation(self, generation: int, data: dict) -> None:
        _write_json(self.generation_path(generation), data)
        with open(self.root / "history.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(data["summary"], ensure_ascii=False) + "\n")
        best = data["population"][0]
        _write_json(
            self.root / "best_genome.json",
            {"generation": generation, **best},
        )

    def load_generation(self, generation: int) -> dict:
        return _read_json(self.generation_path(generation))

    def save_state(self, next_generation: int, population: list[Genome]) -> None:
        _write_json(
            self.state_path,
            {"next_generation": next_generation, "population": [g.to_dict() for g in population]},
        )

    def load_state(self) -> tuple[int, list[Genome]]:
        data = _read_json(self.state_path)
        return data["next_generation"], [Genome.from_dict(d) for d in data["population"]]

    def load_best(self) -> Optional[Genome]:
        path = self.root / "best_genome.json"
        if not path.exists():
            return None
        return Genome.from_dict(_read_json(path))

    def history(self) -> list[dict]:
        path = self.root / "history.jsonl"
        if not path.exists():
            return []
        with open(path, encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
