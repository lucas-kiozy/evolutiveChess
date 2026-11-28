"""Ajuste de Texel dos pesos da avaliação (decisão do Lucas, revisão de 2026-11-28)."""

import random

import pytest

chess = pytest.importorskip("chess")

from luna.adapters import new_game  # noqa: E402
from luna.evaluation import evaluate  # noqa: E402
from luna.genome import Genome  # noqa: E402
from luna.texel import (  # noqa: E402
    TUNED,
    error,
    features,
    fit_k,
    is_quiet,
    positions_from_games,
    tune,
    white_score,
)


def _random_fens(n: int, seed: int = 1) -> list[str]:
    rng = random.Random(seed)
    fens = []
    while len(fens) < n:
        board = chess.Board()
        for _ in range(rng.randrange(6, 90)):
            moves = list(board.legal_moves)
            if not moves:
                break
            board.push(rng.choice(moves))
        if not board.is_game_over() and not board.is_check():
            fens.append(board.fen())
    return fens


def test_features_reproduce_the_evaluation_exactly():
    rng = random.Random(5)
    genomes = [Genome.reference()] + [Genome.random(rng, spread=0.4) for _ in range(5)]
    for fen in _random_fens(60):
        state = new_game("python-chess", fen)
        p = features(state, 0.5)
        for g in genomes:
            expected = evaluate(state, g)
            expected = expected if state.white_to_move else -expected
            assert white_score(p, g.genes) == pytest.approx(expected, abs=1e-6), fen


def test_quiet_positions_have_no_check_and_no_capture():
    assert is_quiet(chess.Board())
    assert not is_quiet(chess.Board("rnbqkbnr/ppp1pppp/8/3p4/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"))


def test_tuning_lowers_the_error_and_stays_in_range():
    # Partidas sintéticas: quem tem mais material ganha. Os pesos devem se ajustar a isso.
    rng = random.Random(2)
    games = []
    for fen in _random_fens(80, seed=3):
        board = chess.Board(fen)
        material = sum(
            (1 if p.color else -1) * {1: 1, 2: 3, 3: 3, 4: 5, 5: 9, 6: 0}[p.piece_type]
            for p in board.piece_map().values()
        )
        winner = "white" if material > 0 else "black" if material < 0 else None
        games.append({"moves": [], "winner": winner, "fen": fen})
    positions = [
        features(
            new_game("python-chess", g["fen"]), {"white": 1.0, "black": 0.0, None: 0.5}[g["winner"]]
        )
        for g in games
    ]
    base = Genome.random(rng, spread=0.3)
    k = fit_k(positions, base.genes)
    tuned, info = tune(positions, base, k=k, step=0.04, min_step=0.01, log=lambda _: None)
    assert info["erro_final"] < info["erro_inicial"]
    assert error(positions, tuned.genes, k) == pytest.approx(info["erro_final"])
    for name in TUNED:
        assert Genome({**tuned.genes}).genes[name] == tuned.genes[name]  # dentro da faixa
    for name in ("quiescence_depth", "contempt", "check_extension", "check_bonus"):
        assert tuned.genes[name] == base.genes[name]  # o Texel não mexe nos genes de busca


def test_positions_come_from_saved_games():
    moves = ["g1f3", "g8f6", "f3g1", "f6g8"] * 8  # sem capturas possíveis: tudo quieto
    positions = positions_from_games([{"moves": moves, "winner": "white"}], per_game=5)
    assert 0 < len(positions) <= 5 and all(p.target == 1.0 for p in positions)
