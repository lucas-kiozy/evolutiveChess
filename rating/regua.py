"""Régua de rating da Luna contra a Leela de 4 e 16 nós (decisão do Lucas em 2026-11-27).

Por que esta régua: a força da Leela limitada por nós não depende do relógio nem da
máquina, e os níveis de 4 e 16 nós ficam perto da força da Luna. Cada partida informa
mais quando o placar esperado está perto de 50% (informação de Fisher ``p(1-p)``), e as
de 1, 128 e 800 nós davam placares extremos. A Leela de 128 nós fica só como marco
ocasional, e o Stockfish (``python -m rating``) continua como teste separado.

Duas fases, as duas retomáveis (cada partida vai para um JSONL assim que termina):

1. **Calibração** (uma vez por rede): cada nível joga contra o Stockfish com
   ``UCI_Elo`` (60+0,6, a escala do resto do projeto), com o Elo do Stockfish
   acompanhando a estimativa do nível e as cores alternadas.
2. **Medição**: a Luna joga pares contra cada nível. As duas partidas do par saem da
   mesma abertura do livro (``luna.openings``) com as cores trocadas, para a sorte da
   abertura se cancelar no par (Glasserman e Yao 1992, *Management Science* 38(6)).

A estimativa é um Bradley–Terry conjunto (Bradley e Terry 1952, *Biometrika*
39:324-345, na escala de Elo): o Stockfish fica fixo no ``UCI_Elo`` de cada partida e
os níveis da Leela e a Luna são livres. Assim a incerteza da calibração entra no erro
da Luna. Uma priori normal fraca (média 2000, desvio 700) só garante que o ótimo exista
com placares extremos. O erro-padrão vem da inversa da matriz de informação no ótimo.

Uso::

    python -m rating.regua calibrar --dir rating/regua --partidas 100
    python -m rating.regua medir --dir rating/regua --nome luna-v5 \\
        --player luna.player:official_factory --pares 32 --erro 25
    python -m rating.regua estimar --dir rating/regua --nome luna-v5
"""

from __future__ import annotations

import argparse
import json
import math
import time
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from pathlib import Path
from typing import Iterable, Optional

LEVELS = (4, 16)
PRIOR_MEAN, PRIOR_SD = 2000.0, 700.0
START_ELO = {4: 2150, 16: 2300}
_K = math.log(10) / 400.0


# ------------------------------------------------------------------ estimativa
def fit(obs: Iterable[tuple[str, Optional[str], float, float]]) -> dict[str, tuple[float, float]]:
    """Bradley–Terry conjunto. ``obs`` = (jogador A, jogador B ou None, Elo fixo de B,
    placar de A). Devolve {jogador: (Elo, erro-padrão)}."""
    obs = list(obs)
    players = sorted({o[0] for o in obs} | {o[1] for o in obs if o[1]})
    if not players:
        return {}
    idx = {p: i for i, p in enumerate(players)}
    n = len(players)
    x = [PRIOR_MEAN] * n
    for _ in range(500):
        grad = [-(xi - PRIOR_MEAN) / PRIOR_SD**2 for xi in x]
        info = [[(1 / PRIOR_SD**2 if i == j else 0.0) for j in range(n)] for i in range(n)]
        for a, b, fixed, s in obs:
            i = idx[a]
            j = idx[b] if b else None
            p = 1 / (1 + math.exp(-_K * (x[i] - (x[j] if j is not None else fixed))))
            w = _K * _K * p * (1 - p)
            grad[i] += _K * (s - p)
            info[i][i] += w
            if j is not None:
                grad[j] -= _K * (s - p)
                info[j][j] += w
                info[i][j] -= w
                info[j][i] -= w
        step = _solve(info, grad)
        step = [max(-200.0, min(200.0, v)) for v in step]  # Newton puro diverge longe do ótimo
        x = [xi + si for xi, si in zip(x, step)]
        if max(abs(v) for v in step) < 1e-6:
            break
    cov = _inverse(info)
    return {p: (x[i], math.sqrt(cov[i][i])) for p, i in idx.items()}


def _solve(a: list[list[float]], b: list[float]) -> list[float]:
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(m[r][c]))
        m[c], m[piv] = m[piv], m[c]
        for r in range(n):
            if r != c:
                f = m[r][c] / m[c][c]
                m[r] = [vr - f * vc for vr, vc in zip(m[r], m[c])]
    return [m[i][n] / m[i][i] for i in range(n)]


def _inverse(a: list[list[float]]) -> list[list[float]]:
    n = len(a)
    cols = [_solve(a, [1.0 if i == j else 0.0 for i in range(n)]) for j in range(n)]
    return [[cols[j][i] for j in range(n)] for i in range(n)]


def observations(rows: Iterable[dict]) -> list[tuple[str, Optional[str], float, float]]:
    out = []
    for r in rows:
        if r["b"].startswith("sf:"):
            out.append((r["a"], None, float(r["sf_elo"]), r["score_a"]))
        else:
            out.append((r["a"], r["b"], 0.0, r["score_a"]))
    return out


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def pair_scores(rows: Iterable[dict]) -> dict[str, list[float]]:
    """Placar médio de cada par completo da Luna, por nível (para conferir o pareamento)."""
    pairs: dict[tuple[str, int], list[float]] = {}
    for r in rows:
        if r["a"] == "luna":
            pairs.setdefault((r["b"], r["pair"]), []).append(r["score_a"])
    out: dict[str, list[float]] = {}
    for (level, _), scores in sorted(pairs.items()):
        if len(scores) == 2:
            out.setdefault(level, []).append(sum(scores) / 2)
    return out


# ------------------------------------------------------------------ partidas
def _play(job: dict) -> dict:
    import chess

    from luna.openings import BOOK
    from rating.leela_opponent import LeelaOpponent
    from rating.match import play_game
    from rating.player import load_factory
    from rating.stockfish_opponent import StockfishOpponent, TimeControl

    def make(spec: str):
        kind, _, arg = spec.partition(":")
        if kind == "leela":
            return LeelaOpponent(int(arg))
        if kind == "sf":
            return StockfishOpponent(int(arg), time_control=TimeControl.parse("60+0.6"))
        return load_factory(job["factory"])()

    a, b = make(job["a"]), make(job["b"])
    board = chess.Board()
    for uci in BOOK[job["opening"]]:
        board.push_uci(uci)
    white, black = (a, b) if job["a_white"] else (b, a)
    t0 = time.monotonic()
    try:
        r = play_game(white, black, start_fen=board.fen())
    finally:
        for p in (a, b):
            close = getattr(p, "close", None)
            if callable(close):
                close()
    s_white = {"1-0": 1.0, "0-1": 0.0}.get(r.result, 0.5)
    score_a = s_white if job["a_white"] else 1.0 - s_white
    return {
        **{k: v for k, v in job.items() if k != "factory"},
        "result": r.result,
        "score_a": score_a,
        "termination": r.termination,
        "plies": r.plies,
        "seconds": round(time.monotonic() - t0, 1),
        "pgn": r.pgn,
    }


def _run(jobs_fn, path: Path, workers: int, stop=lambda rows: False) -> None:
    rows = load(path)
    running: dict = {}
    with ProcessPoolExecutor(max_workers=workers) as ex:
        while True:
            if not stop(rows):
                while len(running) < workers:
                    job = jobs_fn(rows, {j["key"] for j in running.values()})
                    if job is None:
                        break
                    running[ex.submit(_play, job)] = job
            if not running:
                return
            done, _ = wait(running, return_when=FIRST_COMPLETED)
            for fut in done:
                job = running.pop(fut)
                try:
                    rec = fut.result()
                except Exception as exc:  # noqa: BLE001
                    print("ERRO", job["key"], repr(exc), flush=True)
                    continue
                with open(path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(rec) + "\n")
                rows.append(rec)
                print(
                    time.strftime("%H:%M:%S"),
                    rec["key"],
                    rec["result"],
                    rec["termination"],
                    rec["seconds"],
                    flush=True,
                )


def _sf_elo(level: int, rows: list[dict]) -> int:
    obs = [o for o in observations(rows) if o[0] == f"leela:{level}"]
    if not obs:
        return START_ELO.get(level, 2200)
    est = fit(obs)[f"leela:{level}"][0]
    return int(max(1350, min(3150, round(est / 50) * 50)))


def calibrate(directory: Path, games: int, workers: int, levels=LEVELS) -> None:
    path = directory / "calibracao.jsonl"

    def next_job(rows, running):
        done = {r["key"] for r in rows} | running
        for k in range(games):
            for level in levels:
                key = f"cal-{level}-{k}"
                if key not in done:
                    return {
                        "key": key,
                        "a": f"leela:{level}",
                        "b": f"sf:{_sf_elo(level, rows)}",
                        "sf_elo": _sf_elo(level, rows),
                        "a_white": k % 2 == 0,
                        "opening": (k // 2 * 7 + level) % 40,
                    }
        return None

    _run(next_job, path, workers)


def measure(
    directory: Path,
    name: str,
    factory: str,
    pairs: int,
    workers: int,
    target: Optional[float],
    min_pairs: int = 16,
    levels=LEVELS,
) -> None:
    path = directory / f"luna-{name}.jsonl"
    cal = load(directory / "calibracao.jsonl")

    def next_job(rows, running):
        done = {r["key"] for r in rows} | running
        for k in range(pairs):
            for level in levels:
                for g in (0, 1):
                    key = f"{level}-{k}-{g}"
                    if key not in done:
                        return {
                            "key": key,
                            "a": "luna",
                            "b": f"leela:{level}",
                            "pair": k,
                            "a_white": g == 0,
                            "opening": (k * 5 + 3) % 40,
                            "factory": factory,
                        }
        return None

    def stop(rows):
        if target is None:
            return False
        full = min((len(v) for v in pair_scores(rows).values()), default=0)
        if full < min_pairs:
            return False
        return fit(observations(cal + rows))["luna"][1] <= target

    _run(next_job, path, workers, stop)


def report(directory: Path, name: str) -> dict:
    cal = load(directory / "calibracao.jsonl")
    luna = load(directory / f"luna-{name}.jsonl")
    est = fit(observations(cal + luna))
    out = {
        "nome": name,
        "jogadores": {p: {"elo": round(e), "erro": round(s)} for p, (e, s) in est.items()},
    }
    placar = {}
    for r in luna:
        d = placar.setdefault(r["b"], {"V": 0, "E": 0, "D": 0})
        d["V" if r["score_a"] == 1 else "E" if r["score_a"] == 0.5 else "D"] += 1
    out["placar_luna"] = placar
    out["pares_completos"] = {k: len(v) for k, v in pair_scores(luna).items()}
    out["calibracao_partidas"] = {
        f"leela:{lv}": sum(r["a"] == f"leela:{lv}" for r in cal) for lv in LEVELS
    }
    return out


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m rating.regua", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("calibrar", help="níveis da Leela contra o Stockfish")
    c.add_argument("--dir", type=Path, default=Path("rating/regua"))
    c.add_argument("--partidas", type=int, default=100, help="partidas por nível")
    c.add_argument("--paralelo", type=int, default=4)
    m = sub.add_parser("medir", help="a Luna contra cada nível, em pares")
    m.add_argument("--dir", type=Path, default=Path("rating/regua"))
    m.add_argument("--nome", required=True)
    m.add_argument("--player", default="luna.player:official_factory")
    m.add_argument("--pares", type=int, default=32, help="máximo de pares por nível")
    m.add_argument("--erro", type=float, default=25.0, help="para com este erro-padrão")
    m.add_argument("--paralelo", type=int, default=4)
    e = sub.add_parser("estimar", help="imprime a estimativa")
    e.add_argument("--dir", type=Path, default=Path("rating/regua"))
    e.add_argument("--nome", required=True)
    args = ap.parse_args(argv)
    args.dir.mkdir(parents=True, exist_ok=True)
    if args.cmd == "calibrar":
        calibrate(args.dir, args.partidas, args.paralelo)
    elif args.cmd == "medir":
        measure(args.dir, args.nome, args.player, args.pares, args.paralelo, args.erro)
    print(
        json.dumps(report(args.dir, getattr(args, "nome", "")), ensure_ascii=False, indent=2)
        if args.cmd != "calibrar"
        else json.dumps(
            {
                p: {"elo": round(v[0]), "erro": round(v[1])}
                for p, v in fit(observations(load(args.dir / "calibracao.jsonl"))).items()
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
