"""Genoma da Luna: os pesos da função de avaliação e os parâmetros da busca.

Segue a abordagem de David, Koppel e Netanyahu (2014), em que o algoritmo
genético evolui os parâmetros da função de avaliação de um programa de xadrez.
Cada gene é um número com limites; cruzamento uniforme e mutação gaussiana operam
gene a gene.

Os 14 pesos originais vivem num platô: no torneio de 2.760 partidas da análise de
2026-10-08, Lunas com pesos bem diferentes ficaram a no máximo ~30 Elo umas das
outras. A seleção só enxerga diferenças maiores que o ruído das 18 partidas, então
o genoma ganhou genes de efeito grande, como a análise recomendou e o Lucas
aprovou: parâmetros de busca (quiescência, contempt, extensão em xeque) e termos de
final e de segurança do rei. Fogel et al. (2004, Proc. IEEE 92(12):1947-1954) e
David et al. (2014) também evoluíram mais que os valores das peças.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Optional

# nome -> (mínimo, máximo, valor inicial de referência)
# Valores de referência das peças vêm da escala clássica 1/3/3/5/9 em
# centipeões; os demais começam em valores modestos e ficam por conta da
# evolução.
GENE_SPECS: dict[str, tuple[float, float, float]] = {
    "pawn": (70.0, 130.0, 100.0),
    "knight": (200.0, 450.0, 300.0),
    "bishop": (200.0, 450.0, 320.0),
    "rook": (350.0, 700.0, 500.0),
    "queen": (700.0, 1200.0, 900.0),
    "pst_weight": (0.0, 2.0, 1.0),  # peso das tabelas peça-casa
    "mobility": (0.0, 15.0, 4.0),  # por casa atacada
    "bishop_pair": (0.0, 80.0, 30.0),
    "doubled_pawn": (0.0, 50.0, 15.0),  # penalidade
    "isolated_pawn": (0.0, 50.0, 15.0),  # penalidade
    "passed_pawn": (0.0, 100.0, 20.0),  # bônus base, cresce com o avanço
    "rook_open_file": (0.0, 60.0, 20.0),
    "king_shield": (0.0, 40.0, 10.0),  # por peão na frente do rei
    "check_bonus": (-60.0, 60.0, 0.0),  # quanto vale dar xeque
    # Final e segurança do rei
    "passed_pawn_rank": (0.0, 30.0, 5.0),  # bônus extra do peão passado, cresce com o avanço²
    "king_edge": (0.0, 30.0, 10.0),  # com vantagem no final: empurrar o rei inimigo à borda
    "king_proximity": (0.0, 20.0, 4.0),  # com vantagem no final: aproximar o próprio rei
    "king_open_file": (0.0, 60.0, 15.0),  # meio-jogo: coluna sem peão próprio junto ao rei
    # Busca
    "quiescence_depth": (0.0, 8.0, 4.0),  # meios-lances de capturas depois da busca
    "contempt": (0.0, 150.0, 50.0),  # quanto um empate vale de menos para quem busca
    "check_extension": (0.0, 2.0, 1.0),  # extensões por xeque em cada linha da busca
}

GENE_NAMES: tuple[str, ...] = tuple(GENE_SPECS)

#: Genes inteiros: arredondados e, na mutação, mudam pelo menos uma unidade.
INTEGER_GENES = frozenset({"quiescence_depth", "check_extension"})

#: Valor dos genes novos para genomas salvos antes deles (versões, treinos antigos):
#: reproduz exatamente como esses genomas jogavam.
LEGACY_DEFAULTS: dict[str, float] = {
    "passed_pawn_rank": 0.0,
    "king_edge": 0.0,
    "king_proximity": 0.0,
    "king_open_file": 0.0,
    "quiescence_depth": 4.0,
    "contempt": 50.0,
    "check_extension": 0.0,
}


@dataclass
class Genome:
    genes: dict[str, float]
    id: str = ""
    parents: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        missing = set(GENE_NAMES) - set(self.genes)
        if missing:
            raise ValueError(f"Genes faltando: {sorted(missing)}")
        self.genes = {name: clip(name, float(self.genes[name])) for name in GENE_NAMES}

    @classmethod
    def reference(cls, id: str = "ref") -> "Genome":
        return cls({n: spec[2] for n, spec in GENE_SPECS.items()}, id=id)

    @classmethod
    def random(cls, rng: random.Random, id: str = "", spread: float = 0.25) -> "Genome":
        """Genoma perto do de referência, espalhado por ``spread`` da faixa."""
        genes = {}
        for name, (lo, hi, ref) in GENE_SPECS.items():
            genes[name] = ref + rng.gauss(0.0, spread * (hi - lo))
        return cls(genes, id=id)

    def to_dict(self) -> dict:
        return {"id": self.id, "parents": list(self.parents), "genes": dict(self.genes)}

    @classmethod
    def from_dict(cls, data: dict) -> "Genome":
        genes = {**LEGACY_DEFAULTS, **data["genes"]}
        return cls(genes, id=data.get("id", ""), parents=tuple(data.get("parents", ())))


def clip(name: str, value: float) -> float:
    lo, hi, _ = GENE_SPECS[name]
    value = min(hi, max(lo, value))
    return float(round(value)) if name in INTEGER_GENES else value


def crossover(a: Genome, b: Genome, rng: random.Random, id: str = "") -> Genome:
    """Cruzamento uniforme: cada gene vem de um dos pais com chance 1/2."""
    genes = {n: (a.genes[n] if rng.random() < 0.5 else b.genes[n]) for n in GENE_NAMES}
    return Genome(genes, id=id, parents=(a.id, b.id))


def mutate(
    g: Genome,
    rng: random.Random,
    rate: float,
    scale: float,
    id: Optional[str] = None,
) -> Genome:
    """Mutação gaussiana: cada gene muda com probabilidade ``rate`` e desvio
    ``scale`` vezes a largura da faixa do gene; o valor é recortado aos limites.
    Um gene inteiro que muta anda pelo menos uma unidade, senão o arredondamento
    desfaria quase toda mutação em faixas curtas como 0 a 2."""
    genes = dict(g.genes)
    for name, (lo, hi, _) in GENE_SPECS.items():
        if rng.random() < rate:
            step = rng.gauss(0.0, scale * (hi - lo))
            if name in INTEGER_GENES:
                step = round(step) or rng.choice((-1, 1))
            genes[name] = genes[name] + step
    return Genome(genes, id=g.id if id is None else id, parents=g.parents)
