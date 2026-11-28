"""Protocolo pré-registrado da catraca (revisão do AG de 2026-11-28)."""

import random

import pytest

from luna import promotion
from luna.genome import Genome
from luna.promotion import PROTOCOL, PromotionConfig, corrected_elo, run_promotion_match


def _fake_pairs(edge: float):
    """Troca as partidas por sorteios: a candidata faz ``edge`` dos pontos por partida."""

    def fake(args):
        _, _, _, _, seed = args
        rng = random.Random(seed)
        s1 = 1.0 if rng.random() < edge else 0.0
        s2 = 1.0 if rng.random() < edge else 0.0
        return s1, s2, {"seed": seed}, {"seed": seed}

    return fake


def _genomes():
    a = Genome(dict(Genome.reference().genes), id="cand")
    b = Genome(dict(Genome.reference().genes), id="ofic")
    return a, b


def test_each_challenge_gets_new_pairs_unless_the_seed_is_fixed(monkeypatch):
    monkeypatch.setattr(promotion, "_pair_task", _fake_pairs(0.5))
    a, b = _genomes()
    cfg = PromotionConfig(max_games=64, sequential=False)
    first = run_promotion_match(a, b, cfg, workers=1, log=lambda _: None)
    other = Genome(dict(a.genes), id="cand2")
    second = run_promotion_match(other, b, cfg, workers=1, log=lambda _: None)
    assert first.config["seed_used"] != second.config["seed_used"]
    assert first.games_detail != second.games_detail
    assert first.config["protocol"] == PROTOCOL
    fixed = PromotionConfig(max_games=64, sequential=False, seed=7)
    x = run_promotion_match(a, b, fixed, workers=1, log=lambda _: None)
    y = run_promotion_match(other, b, fixed, workers=1, log=lambda _: None)
    assert x.games_detail == y.games_detail


def test_fixed_mode_plays_all_games_and_never_promotes(monkeypatch):
    monkeypatch.setattr(promotion, "_pair_task", _fake_pairs(0.9))
    a, b = _genomes()
    result = run_promotion_match(
        a, b, PromotionConfig(max_games=64, sequential=False), workers=1, log=lambda _: None
    )
    assert result.games == 64 and not result.promoted and result.decision == "teto"


def test_h1_needs_confirmation_with_new_pairs(monkeypatch):
    monkeypatch.setattr(promotion, "_pair_task", _fake_pairs(0.7))
    a, b = _genomes()
    cfg = PromotionConfig(max_games=400, bias_sims=50)
    result = run_promotion_match(a, b, cfg, workers=1, log=lambda _: None)
    assert result.decision == "H1" and result.confirmation["decision"] == "H1"
    assert result.promoted
    seeds = [g["seed"] for g in result.games_detail]
    assert len(set(seeds)) == len(seeds) // 2  # pares novos na confirmação
    no_confirm = run_promotion_match(
        a,
        b,
        PromotionConfig(max_games=400, confirm=False, bias_sims=50),
        workers=1,
        log=lambda _: None,
    )
    assert no_confirm.promoted and no_confirm.confirmation is None


def test_a_challenge_resumes_from_its_pairs_file(monkeypatch, tmp_path):
    monkeypatch.setattr(promotion, "_pair_task", _fake_pairs(0.5))
    a, b = _genomes()
    out = tmp_path / "desafio"
    full = run_promotion_match(
        a, b, PromotionConfig(max_games=64, sequential=False), workers=1, log=lambda _: None
    )
    half = PromotionConfig(max_games=32, sequential=False, out_dir=str(out))
    run_promotion_match(a, b, half, workers=1, log=lambda _: None)
    resumed = run_promotion_match(
        a,
        b,
        PromotionConfig(max_games=64, sequential=False, out_dir=str(out)),
        workers=1,
        log=lambda _: None,
    )
    assert resumed.games_detail == full.games_detail
    assert (out / "resultado.json").exists()


def test_corrected_elo_shrinks_an_early_stop():
    # Um teste que parou cedo com placar alto superestima o Elo.
    rng = random.Random(3)
    pairs = [rng.choice((0.5, 0.75, 1.0, 0.5)) for _ in range(40)]
    observed, _ = promotion.elo_estimate(pairs)
    fixed = corrected_elo(pairs, PromotionConfig(bias_sims=200), "H1")
    assert fixed is not None and fixed < observed
    assert corrected_elo(pairs, PromotionConfig(), "teto") is None
    assert corrected_elo(pairs[:4], PromotionConfig(), "H1") is None


@pytest.mark.parametrize("flag", ["--fixo", "--sem-confirmacao"])
def test_cli_accepts_the_protocol_flags(flag):
    from luna.__main__ import main

    with pytest.raises(SystemExit):  # sem candidata: para antes de jogar
        main(["promote", flag, "--candidate", "luna-v1", "--run-dir", "x"])
