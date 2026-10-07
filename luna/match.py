"""Uma partida Luna contra Luna."""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field
from typing import Optional

from luna.adapters import DEFAULT_BACKEND, new_game
from luna.genome import Genome
from luna.search import SearchConfig, Searcher

_STANDARD_VALUE = {"P": 1, "N": 3, "B": 3, "R": 5, "Q": 9, "K": 0}


@dataclass
class MatchConfig:
    search: SearchConfig = field(default_factory=SearchConfig)
    max_plies: int = 200  # limite de meios-lances; ao atingir, empate por limite
    random_opening_plies: int = 2  # lances aleatórios no começo para variar as partidas
    backend: str = DEFAULT_BACKEND


@dataclass
class GameRecord:
    white_id: str
    black_id: str
    winner: Optional[str]  # "white", "black" ou None (empate)
    termination: str
    plies: int
    white_checks: int
    black_checks: int
    mate_moves: Optional[int]  # lances do vencedor até o mate; None se não houve mate
    material_balance: int  # material das brancas menos das pretas (escala 1/3/3/5/9)
    moves: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def play_game(
    white: Genome,
    black: Genome,
    config: MatchConfig,
    seed: Optional[int] = None,
) -> GameRecord:
    rng = random.Random(seed)
    state = new_game(config.backend)
    searchers = {
        True: Searcher(white, config.search, rng),
        False: Searcher(black, config.search, rng),
    }
    checks = {True: 0, False: 0}
    moves: list[str] = []

    outcome = None
    while state.ply < config.max_plies:
        outcome = state.outcome(claim_draw=True)
        if outcome is not None:
            break
        mover = state.white_to_move
        if state.ply < config.random_opening_plies:
            move = rng.choice(state.legal_moves())
        else:
            move = searchers[mover].choose_move(state)
            if move is None:  # não deveria acontecer: outcome já cobre sem lances
                break
        state.push(move)
        moves.append(move)
        if state.is_check():
            checks[mover] += 1
    else:
        outcome = state.outcome(claim_draw=True)

    plies = state.ply
    if outcome is None:
        winner, termination = None, "max_plies"
    else:
        winner = None if outcome.winner is None else ("white" if outcome.winner else "black")
        termination = outcome.termination

    mate_moves = None
    if termination == "checkmate":
        mate_moves = (plies + 1) // 2 if winner == "white" else plies // 2

    balance = 0
    for _, piece, is_white in state.pieces():
        balance += _STANDARD_VALUE[piece] if is_white else -_STANDARD_VALUE[piece]

    return GameRecord(
        white_id=white.id,
        black_id=black.id,
        winner=winner,
        termination=termination,
        plies=plies,
        white_checks=checks[True],
        black_checks=checks[False],
        mate_moves=mate_moves,
        material_balance=balance,
        moves=moves,
    )
