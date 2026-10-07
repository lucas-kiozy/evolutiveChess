"""Joga uma partida do Lichess do começo ao fim com um ``MovePlayer``."""

from __future__ import annotations

import logging
from typing import Optional

import chess

from lichess_bot.client import LichessClient, LichessError
from lichess_bot.learning import GameRecord, build_record
from rating.player import MovePlayer

log = logging.getLogger(__name__)

#: Status do Lichess que significam "ainda em andamento".
RUNNING = {"created", "started"}


class GameRunner:
    def __init__(self, client: LichessClient, player: MovePlayer, game_id: str, my_id: str):
        self.client = client
        self.player = player
        self.game_id = game_id
        self.my_id = my_id.lower()
        self.color: Optional[str] = None
        self.initial_fen = chess.STARTING_FEN
        self.meta: dict = {}
        self.moves: list[str] = []
        self.status = "started"
        self.winner: Optional[str] = None

    # ----------------------------------------------------------------- setup
    def _on_full(self, ev: dict) -> None:
        white = ev.get("white") or {}
        black = ev.get("black") or {}
        self.color = "white" if (white.get("id") or "").lower() == self.my_id else "black"
        me, opp = (white, black) if self.color == "white" else (black, white)
        fen = ev.get("initialFen") or "startpos"
        self.initial_fen = chess.STARTING_FEN if fen == "startpos" else fen
        self.meta = {
            "rated": bool(ev.get("rated")),
            "speed": ev.get("speed") or "",
            "opponent": opp.get("name") or opp.get("id") or "",
            "opponent_rating": opp.get("rating"),
            "luna_rating": me.get("rating"),
        }
        hook = getattr(self.player, "new_game", None)
        if callable(hook):
            hook(chess.WHITE if self.color == "white" else chess.BLACK)
        if (ev.get("variant") or {}).get("key", "standard") != "standard":
            log.warning("Variante não suportada em %s; abandonando.", self.game_id)
            self._safe(self.client.resign)
            return
        self._on_state(ev.get("state") or {})

    def _on_state(self, st: dict) -> None:
        self.moves = (st.get("moves") or "").split()
        self.status = st.get("status") or self.status
        self.winner = st.get("winner")
        if self.status not in RUNNING:
            return
        board = chess.Board(self.initial_fen)
        for uci in self.moves:
            board.push_uci(uci)
        my_turn = board.turn == (chess.WHITE if self.color == "white" else chess.BLACK)
        if not my_turn or board.is_game_over():
            return
        self._play(board, st)

    def _play(self, board: chess.Board, st: dict) -> None:
        legal = [m.uci() for m in board.legal_moves]
        set_clock = getattr(self.player, "set_clock", None)
        if callable(set_clock):
            mine = "w" if self.color == "white" else "b"
            set_clock(st.get(f"{mine}time"), st.get(f"{mine}inc"))
        try:
            move = self.player.choose_move(board.fen(), legal)
        except Exception:  # noqa: BLE001
            log.exception("Jogador falhou em %s; jogando o primeiro lance legal.", self.game_id)
            move = legal[0]
        if move not in legal:
            log.error("Lance ilegal %r do jogador; usando %s.", move, legal[0])
            move = legal[0]
        try:
            self.client.make_move(self.game_id, move)
        except LichessError as exc:
            # Pode acontecer se a partida acabou entre o estado e o lance.
            log.warning("Lance %s recusado em %s: %s", move, self.game_id, exc)

    def _safe(self, fn) -> None:
        try:
            fn(self.game_id)
        except LichessError as exc:
            log.warning("%s falhou em %s: %s", fn.__name__, self.game_id, exc)

    # ------------------------------------------------------------------ loop
    def run(self) -> GameRecord:
        for ev in self.client.stream_game(self.game_id):
            kind = ev.get("type")
            if kind == "gameFull":
                self._on_full(ev)
            elif kind == "gameState":
                self._on_state(ev)
            elif kind == "opponentGone":
                if ev.get("gone") and ev.get("claimWinInSeconds") == 0:
                    self._safe(self.client.claim_victory)
            if self.status not in RUNNING:
                break
        return build_record(
            self.game_id,
            self.color or "white",
            self.moves,
            self.status,
            self.winner,
            initial_fen=self.initial_fen,
            **self.meta,
        )
