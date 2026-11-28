"""Ajuste supervisionado dos pesos da avaliação pelo método de Texel.

Decisão do Lucas em 2026-11-27, confirmada na revisão do AG de 2026-11-28: os 14
pesos originais vivem num platô em que o algoritmo genético anda por deriva (o ruído
de 18 partidas por Luna esconde efeitos de poucos Elo). O ajuste de Texel dá a esses
pesos uma aptidão determinística e sem ruído de partida, e o AG fica com os genes de
busca, em que a seleção mostrou efeito. É a mesma ideia de David et al. (2014, IEEE
Trans. Evol. Comput. 18(5):779-789), que ajustaram a avaliação com posições e notas em
vez de só partidas.

Método (Chess Programming Wiki, "Texel's Tuning Method"; fonte técnica, sem artigo
revisado próprio):

- posições quietas (sem xeque e sem captura possível) tiradas de partidas, cada uma
  com o resultado da partida do ponto de vista das brancas (1, 1/2 ou 0) ou, com o
  Stockfish, a chance de vitória da nota dele;
- erro = média de (resultado - sigmoide(K x avaliação))², com K ajustado antes para os
  pesos de partida;
- busca local: cada peso anda um passo para cima ou para baixo se o erro cair; sem
  melhora numa volta, o passo cai pela metade.

Para ser rápido em Python, a avaliação é decomposta em atributos da posição
(contagens, somas das tabelas, estrutura de peões...), extraídos uma vez. A combinação
com os pesos reproduz ``luna.evaluation.evaluate`` exatamente (há teste disso), inclusive
a troca para o final, que depende dos valores de torre e bispo.

O genoma ajustado é só uma candidata: só vira oficial pela catraca (docs/CATRACA.md).

Uso::

    python -m luna.texel --partidas DIR_DO_TREINO [DIR ...] --base luna-v5 \\
        --saida luna/versions/candidata-texel.json --posicoes 40000
"""

from __future__ import annotations

import argparse
import datetime
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence

from luna.adapters import new_game
from luna.evaluation import PIECE_GENE, PST_BLACK, PST_WHITE, _is_passed, _king_shield
from luna.genome import GENE_SPECS, Genome

#: Pesos que o Texel ajusta: a avaliação, menos check_bonus (as posições quietas não
#: têm xeque, então ele não aparece nos dados). Os genes de busca ficam com o AG.
TUNED = (
    "pawn",
    "knight",
    "bishop",
    "rook",
    "queen",
    "pst_weight",
    "mobility",
    "bishop_pair",
    "doubled_pawn",
    "isolated_pawn",
    "passed_pawn",
    "rook_open_file",
    "king_shield",
    "passed_pawn_rank",
    "king_edge",
    "king_proximity",
    "king_open_file",
)
_PIECES = ("P", "N", "B", "R", "Q")


@dataclass
class Position:
    """Atributos de uma posição, do ponto de vista das brancas (brancas - pretas)."""

    counts: tuple[tuple[int, ...], tuple[int, ...]]  # (pretas, brancas) por P N B R Q
    pst: float  # tabelas peça-casa sem o rei
    king_mid: float
    king_end: float
    bishop_pair: int
    doubled: int
    isolated: int
    passed: float  # soma de avanço/6
    passed_rank: float  # soma de avanço²/6
    rook_open: float  # bônus de coluna aberta/2
    shield: int  # só no meio-jogo
    open_king: int  # só no meio-jogo
    center: tuple[int, int]  # distância do rei (preto, branco) ao centro, 0 a 6
    king_distance: int
    mobility: int
    target: float  # resultado (ou chance de vitória) das brancas, 0 a 1


def features(state, target: float) -> Position:
    """Atributos de ``state`` (um ``GameState``), iguais aos de ``evaluate``."""
    counts = [[0] * 5, [0] * 5]
    pst = 0.0
    pawn_files = [[0] * 8, [0] * 8]
    pawns: list[list[int]] = [[], []]
    rooks: list[list[int]] = [[], []]
    kings = [0, 0]
    for square, piece, white in state.pieces():
        side = 1 if white else 0
        if piece == "K":
            kings[side] = square
            continue
        counts[side][_PIECES.index(piece)] += 1
        table = PST_WHITE if white else PST_BLACK
        pst += (1 if white else -1) * table[piece][square]
        if piece == "P":
            pawn_files[side][square & 7] += 1
            pawns[side].append(square)
        elif piece == "R":
            rooks[side].append(square)
    king_mid = PST_WHITE["K"][kings[1]] - PST_BLACK["K"][kings[0]]
    king_end = PST_WHITE["K_END"][kings[1]] - PST_BLACK["K_END"][kings[0]]
    terms = {k: 0.0 for k in ("doubled", "isolated", "passed", "passed_rank", "rook", "sh", "ok")}
    for side, sign in ((1, 1), (0, -1)):
        files, enemy = pawn_files[side], pawn_files[1 - side]
        terms["doubled"] += sign * sum(c - 1 for c in files if c > 1)
        iso = 0
        for f, c in enumerate(files):
            if c and not ((f > 0 and files[f - 1]) or (f < 7 and files[f + 1])):
                iso += c
        terms["isolated"] += sign * iso
        for sq in pawns[side]:
            if _is_passed(sq, side, pawns[1 - side]):
                rank = sq >> 3
                adv = rank if side == 1 else 7 - rank
                terms["passed"] += sign * adv / 6.0
                terms["passed_rank"] += sign * adv * adv / 6.0
        bonus = 0
        for sq in rooks[side]:
            f = sq & 7
            if files[f] == 0:
                bonus += 1 if enemy[f] else 2
        terms["rook"] += sign * bonus / 2.0
        terms["sh"] += sign * _king_shield(kings[side], side, pawns[side])
        kf = kings[side] & 7
        near = range(max(0, kf - 1), min(7, kf + 1) + 1)
        terms["ok"] += sign * sum(1 for f in near if not files[f])

    def center(k: int) -> int:
        f, r = k & 7, k >> 3
        return max(3 - f, f - 4) + max(3 - r, r - 4)

    distance = abs((kings[0] & 7) - (kings[1] & 7)) + abs((kings[0] >> 3) - (kings[1] >> 3))
    return Position(
        counts=(tuple(counts[0]), tuple(counts[1])),
        pst=pst,
        king_mid=king_mid,
        king_end=king_end,
        bishop_pair=(counts[1][2] >= 2) - (counts[0][2] >= 2),
        doubled=int(terms["doubled"]),
        isolated=int(terms["isolated"]),
        passed=terms["passed"],
        passed_rank=terms["passed_rank"],
        rook_open=terms["rook"],
        shield=int(terms["sh"]),
        open_king=int(terms["ok"]),
        center=(center(kings[0]), center(kings[1])),
        king_distance=distance,
        mobility=state.mobility(True) - state.mobility(False),
        target=target,
    )


def white_score(p: Position, g: dict[str, float]) -> float:
    """Avaliação das brancas, igual a ``evaluate`` (sem o termo de xeque)."""
    values = [g[PIECE_GENE[x]] for x in _PIECES]
    black, white = p.counts
    material = sum(v * (w - b) for v, w, b in zip(values, white, black))
    non_pawn = sum(v * (w + b) for v, w, b in zip(values[1:], white[1:], black[1:]))
    endgame = non_pawn <= 2 * g["rook"] + g["bishop"]
    score = material + g["pst_weight"] * (p.pst + (p.king_end if endgame else p.king_mid))
    score += g["bishop_pair"] * p.bishop_pair
    score += (
        -g["doubled_pawn"] * p.doubled
        - g["isolated_pawn"] * p.isolated
        + g["passed_pawn"] * p.passed
        + g["passed_pawn_rank"] * p.passed_rank
        + g["rook_open_file"] * p.rook_open
    )
    if not endgame:
        score += g["king_shield"] * p.shield - g["king_open_file"] * p.open_king
    elif (g["king_edge"] or g["king_proximity"]) and abs(material) >= g["bishop"]:
        strong = 1 if material > 0 else 0
        mop = g["king_edge"] * p.center[1 - strong] + g["king_proximity"] * (14 - p.king_distance)
        score += mop if strong else -mop
    score += g["mobility"] * p.mobility
    return score


def sigmoid(score: float, k: float) -> float:
    return 1.0 / (1.0 + 10.0 ** (-k * score / 400.0))


def error(positions: Sequence[Position], genes: dict[str, float], k: float) -> float:
    total = 0.0
    for p in positions:
        d = p.target - sigmoid(white_score(p, genes), k)
        total += d * d
    return total / len(positions)


def fit_k(positions: Sequence[Position], genes: dict[str, float]) -> float:
    """K que minimiza o erro com os pesos de partida (busca por seção áurea)."""
    lo, hi = 0.05, 3.0
    phi = (math.sqrt(5) - 1) / 2
    a, b = hi - phi * (hi - lo), lo + phi * (hi - lo)
    fa, fb = error(positions, genes, a), error(positions, genes, b)
    for _ in range(40):
        if fa < fb:
            hi, b, fb = b, a, fa
            a = hi - phi * (hi - lo)
            fa = error(positions, genes, a)
        else:
            lo, a, fa = a, b, fb
            b = lo + phi * (hi - lo)
            fb = error(positions, genes, b)
    return (lo + hi) / 2


def tune(
    positions: Sequence[Position],
    base: Genome,
    k: Optional[float] = None,
    step: float = 0.02,
    min_step: float = 0.00125,
    max_rounds: int = 200,
    log=print,
) -> tuple[Genome, dict]:
    """Busca local de Texel sobre os pesos de ``TUNED``. ``step`` é a fração da faixa de
    cada gene; os valores ficam dentro das faixas do genoma."""
    genes = dict(base.genes)
    k = k if k is not None else fit_k(positions, genes)
    best = error(positions, genes, k)
    start = best
    rounds = 0
    while step >= min_step and rounds < max_rounds:
        rounds += 1
        improved = False
        for name in TUNED:
            lo, hi, _ = GENE_SPECS[name]
            delta = step * (hi - lo)
            for direction in (1, -1):
                trial = min(hi, max(lo, genes[name] + direction * delta))
                if trial == genes[name]:
                    continue
                old = genes[name]
                genes[name] = trial
                e = error(positions, genes, k)
                if e < best:
                    best, improved = e, True
                    break
                genes[name] = old
        log(f"volta {rounds}: erro {best:.6f} (passo {step:g} da faixa)")
        if not improved:
            step /= 2
    info = {"k": k, "erro_inicial": start, "erro_final": best, "voltas": rounds}
    return Genome(genes, id=f"{base.id or 'base'}-texel"), info


def is_quiet(board) -> bool:
    """Sem xeque e sem captura possível: a avaliação estática vale como a da quiescência."""
    if board.is_check():
        return False
    return not any(board.is_capture(m) for m in board.legal_moves)


def positions_from_games(
    games: Iterable[dict],
    per_game: int = 8,
    skip_plies: int = 10,
    rng: Optional[random.Random] = None,
    engine=None,
    engine_depth: int = 12,
) -> list[Position]:
    """Até ``per_game`` posições quietas por partida, sorteadas depois de ``skip_plies``.
    Com ``engine`` (um ``chess.engine.SimpleEngine``, como o Stockfish), o alvo é a
    chance de vitória das brancas pela nota dele, e não o resultado da partida."""
    import chess
    import chess.engine

    rng = rng or random.Random(0)
    result_of = {"white": 1.0, "black": 0.0, None: 0.5}
    out: list[Position] = []
    for game in games:
        moves = game.get("moves") or []
        if len(moves) <= skip_plies:
            continue
        board = chess.Board()
        candidates = []
        for ply, uci in enumerate(moves):
            if ply >= skip_plies and is_quiet(board):
                candidates.append(board.fen())
            board.push_uci(uci)
        target = result_of[game.get("winner")]
        for fen in rng.sample(candidates, min(per_game, len(candidates))):
            if engine is not None:
                info = engine.analyse(chess.Board(fen), chess.engine.Limit(depth=engine_depth))
                target = info["score"].white().wdl().expectation()
            out.append(features(new_game("python-chess", fen), target))
    return out


def load_games(dirs: Iterable[str]) -> list[dict]:
    """Partidas de ``generations/gen_*.json`` de treinos (ou de arquivos .json soltos)."""
    games: list[dict] = []
    for d in dirs:
        path = Path(d)
        files = sorted(path.glob("generations/gen_*.json")) if path.is_dir() else [path]
        for f in files:
            games += json.loads(f.read_text(encoding="utf-8")).get("games", [])
    return games


def main(argv: Optional[list[str]] = None) -> None:
    from luna.versions import LunaVersion, load_version

    ap = argparse.ArgumentParser(prog="python -m luna.texel", description=__doc__.splitlines()[0])
    ap.add_argument("--partidas", nargs="+", required=True, help="pastas de treino ou .json")
    ap.add_argument("--base", default="luna-v5", help="versão de partida (nome ou caminho)")
    ap.add_argument("--saida", required=True, help="arquivo da versão candidata")
    ap.add_argument("--nome", default=None, help="padrão: <base>-texel")
    ap.add_argument("--posicoes", type=int, default=40000, help="máximo de posições")
    ap.add_argument("--por-partida", type=int, default=8)
    ap.add_argument("--validacao", type=float, default=0.2, help="fração guardada para validar")
    ap.add_argument("--semente", type=int, default=0)
    ap.add_argument("--stockfish", help="caminho do Stockfish: alvo pela nota dele")
    ap.add_argument("--profundidade-stockfish", type=int, default=12)
    args = ap.parse_args(argv)

    rng = random.Random(args.semente)
    base_v = load_version(args.base)
    games = load_games(args.partidas)
    rng.shuffle(games)
    engine = None
    if args.stockfish:
        import chess.engine

        engine = chess.engine.SimpleEngine.popen_uci(args.stockfish)
        # Só as partidas necessárias: o Stockfish custa por posição.
        games = games[: max(1, args.posicoes // max(1, args.por_partida)) * 2]
    try:
        positions = positions_from_games(
            games,
            args.por_partida,
            rng=rng,
            engine=engine,
            engine_depth=args.profundidade_stockfish,
        )[: args.posicoes]
    finally:
        if engine is not None:
            engine.quit()
    if len(positions) < 100:
        raise SystemExit(f"poucas posições quietas ({len(positions)})")
    cut = int(len(positions) * (1 - args.validacao))
    train, valid = positions[:cut], positions[cut:]
    print(f"{len(games)} partidas, {len(train)} posições de ajuste e {len(valid)} de validação")
    tuned, info = tune(train, base_v.genome)
    info["validacao_inicial"] = error(valid, base_v.genome.genes, info["k"])
    info["validacao_final"] = error(valid, tuned.genes, info["k"])
    print(json.dumps(info, indent=2))
    name = args.nome or f"{base_v.name}-texel"
    version = LunaVersion(
        name=name,
        genome=Genome(dict(tuned.genes), id=name),
        search=base_v.search,
        source={
            "texel": info,
            "base": base_v.name,
            "partidas": args.partidas,
            "alvo": "stockfish" if args.stockfish else "resultado",
        },
        created=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        notes="Pesos da avaliação ajustados pelo método de Texel; candidata para a catraca.",
    )
    Path(args.saida).write_text(
        json.dumps(version.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Candidata salva em {args.saida}")


if __name__ == "__main__":
    main()
