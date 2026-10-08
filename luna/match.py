"""Uma partida Luna contra Luna."""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field
from typing import Optional, Sequence

from luna.adapters import DEFAULT_BACKEND, new_game
from luna.genome import Genome
from luna.resign import RESIGN_MOVES, RESIGN_SCORE, ResignTracker, should_resign
from luna.search import SearchConfig, Searcher

_STANDARD_VALUE = {"P": 1, "N": 3, "B": 3, "R": 5, "Q": 9, "K": 0}


@dataclass
class MatchConfig:
    search: SearchConfig = field(default_factory=SearchConfig)
    max_plies: int = 200  # limite de meios-lances; ao atingir, empate por limite
    random_opening_plies: int = 2  # lances aleatórios no começo para variar as partidas
    backend: str = DEFAULT_BACKEND
    # Desistência (luna.resign): avaliação <= resign_score por resign_moves lances
    # seguidos, sem empate forçado à vista. resign_moves = 0 desliga.
    resign_score: float = RESIGN_SCORE
    resign_moves: int = RESIGN_MOVES


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
    white_captures: dict[str, int] = field(default_factory=dict)  # peças pretas capturadas
    black_captures: dict[str, int] = field(default_factory=dict)  # peças brancas capturadas

    def to_dict(self) -> dict:
        return asdict(self)


def play_game(
    white: Genome,
    black: Genome,
    config: MatchConfig,
    seed: Optional[int] = None,
    opening: Sequence[str] = (),
) -> GameRecord:
    """Joga uma partida. ``opening`` são lances UCI de livro jogados antes de tudo; os
    ``random_opening_plies`` lances aleatórios vêm depois deles."""
    rng = random.Random(seed)
    state = new_game(config.backend)
    searchers = {
        True: Searcher(white, config.search, rng),
        False: Searcher(black, config.search, rng),
    }
    trackers = {}
    if config.resign_moves > 0:
        trackers = {
            side: ResignTracker(config.resign_score, config.resign_moves) for side in (True, False)
        }
    resigned: Optional[bool] = None  # cor de quem desistiu
    checks = {True: 0, False: 0}
    captures: dict[bool, dict[str, int]] = {True: {}, False: {}}
    moves: list[str] = []
    for uci in opening:
        state.push(state.parse_uci(uci))
        moves.append(uci)
    random_until = len(opening) + config.random_opening_plies

    outcome = None
    while state.ply < config.max_plies:
        outcome = state.outcome(claim_draw=True)
        if outcome is not None:
            break
        mover = state.white_to_move
        if state.ply < random_until:
            move = rng.choice(sorted(state.legal_moves(), key=state.uci))
        else:
            move = searchers[mover].choose_move(state)
            if move is None:  # não deveria acontecer: outcome já cobre sem lances
                break
            score = searchers[mover].last_score
            if trackers and should_resign(trackers[mover], score, state):
                resigned = mover
                break
        victim = state.captured_piece(move)
        if victim:
            captures[mover][victim] = captures[mover].get(victim, 0) + 1
        state.push(move)
        moves.append(state.uci(move))
        if state.is_check():
            checks[mover] += 1
    else:
        outcome = state.outcome(claim_draw=True)

    plies = state.ply
    if resigned is not None:
        winner, termination = ("black" if resigned else "white"), "resignation"
    elif outcome is None:
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
        white_captures=captures[True],
        black_captures=captures[False],
    )
