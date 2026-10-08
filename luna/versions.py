"""Versões nomeadas da Luna.

Um treino (``run_dir``) é temporário e grande. Uma versão é um arquivo JSON
pequeno em ``luna/versions/<nome>.json`` com tudo o que é preciso para a Luna
jogar exatamente como jogava: o genoma, a configuração da busca e de onde ela
veio (treino, geração, estatísticas). Esse arquivo vai para o repositório, então
cada versão fica guardada no histórico do git.
"""

from __future__ import annotations

import datetime
import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from luna.evolution import EvolutionConfig
from luna.genome import Genome
from luna.search import SearchConfig
from luna.storage import RunStorage

VERSIONS_DIR = Path(__file__).resolve().parent / "versions"
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


@dataclass
class LunaVersion:
    name: str
    genome: Genome
    search: SearchConfig
    source: dict  # run_dir, geração, id, estatísticas, backend
    created: str
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "created": self.created,
            "notes": self.notes,
            "source": self.source,
            "search": asdict(self.search),
            "genome": self.genome.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "LunaVersion":
        return cls(
            name=d["name"],
            genome=Genome.from_dict(d["genome"]),
            search=SearchConfig.from_dict(d["search"]),
            source=d.get("source", {}),
            created=d.get("created", ""),
            notes=d.get("notes", ""),
        )


def version_from_run(
    run_dir: str | Path,
    name: Optional[str] = None,
    generation: Optional[int] = None,
    notes: str = "",
) -> LunaVersion:
    """A melhor Luna de uma geração (padrão: a última avaliada), ainda sem salvar."""
    storage = RunStorage(run_dir)
    config = storage.load_config()
    history = storage.history()
    if not history:
        raise ValueError(f"{run_dir} ainda não tem nenhuma geração avaliada")
    if generation is None:
        generation = history[-1]["generation"]
    data = storage.load_generation(generation)
    best = data["population"][0]
    return LunaVersion(
        name=name or f"luna-g{generation:04d}",
        genome=Genome.from_dict(best),
        search=EvolutionConfig.from_dict(config).match.search,
        source={
            "run_dir": str(run_dir),
            "generation": generation,
            "id": best["id"],
            "rank": best.get("rank"),
            "stats": best.get("stats"),
            "backend": config["match"].get("backend"),
            "summary": data.get("summary"),
        },
        created=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        notes=notes,
    )


def export_version(
    run_dir: str | Path,
    name: Optional[str] = None,
    generation: Optional[int] = None,
    notes: str = "",
    versions_dir: str | Path = VERSIONS_DIR,
    overwrite: bool = False,
) -> Path:
    """Salva a melhor Luna de uma geração (padrão: a última avaliada) como versão."""
    return save_version(version_from_run(run_dir, name, generation, notes), versions_dir, overwrite)


def load_version(name_or_path: str | Path, versions_dir: str | Path = VERSIONS_DIR) -> LunaVersion:
    """Carrega uma versão pelo nome (``luna-v1``) ou pelo caminho do arquivo."""
    path = Path(name_or_path)
    if not path.suffix:
        path = Path(versions_dir) / f"{name_or_path}.json"
    return LunaVersion.from_dict(json.loads(path.read_text(encoding="utf-8")))


def list_versions(versions_dir: str | Path = VERSIONS_DIR) -> list[LunaVersion]:
    folder = Path(versions_dir)
    if not folder.exists():
        return []
    return [load_version(p) for p in sorted(folder.glob("*.json"))]


OFFICIAL_FILE = "oficial.txt"


def official_name(versions_dir: str | Path = VERSIONS_DIR) -> str:
    """Nome da Luna oficial, a que joga as partidas que contam (rating e Lichess).

    Só muda pela catraca de promoção (``python -m luna promote``)."""
    return (Path(versions_dir) / OFFICIAL_FILE).read_text(encoding="utf-8").strip()


def set_official(name: str, versions_dir: str | Path = VERSIONS_DIR) -> None:
    load_version(name, versions_dir)  # falha se a versão não existir
    path = Path(versions_dir) / OFFICIAL_FILE
    tmp = path.with_suffix(".txt.tmp")
    tmp.write_text(name + "\n", encoding="utf-8")
    os.replace(tmp, path)


def version_path(name: str, versions_dir: str | Path = VERSIONS_DIR) -> Path:
    if not _NAME.match(name):
        raise ValueError("nome deve ter letras, números, ponto, hífen ou sublinhado")
    return Path(versions_dir) / f"{name}.json"


def save_version(
    version: LunaVersion, versions_dir: str | Path = VERSIONS_DIR, overwrite: bool = False
) -> Path:
    path = version_path(version.name, versions_dir)
    if path.exists() and not overwrite:
        raise FileExistsError(f"A versão {version.name} já existe: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(version.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(tmp, path)
    return path
