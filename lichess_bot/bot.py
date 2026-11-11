"""Laço principal: uma partida por vez, aprendendo depois de cada uma.

* Uma thread lê o stream de eventos e responde desafios na hora: aceita se a
  Luna está livre e o desafio cabe na configuração; recusa com ``later``
  quando já há partida em andamento (Lucas pediu partida de cada vez).
* A thread principal joga as partidas em fila e, ao fim de cada uma, chama o
  aprendiz (``Learner.on_game_finished``).
"""

from __future__ import annotations

import logging
import queue
import random
import threading
import time
from typing import Callable, Optional

from lichess_bot.client import LichessClient, LichessError
from lichess_bot.config import BotConfig
from lichess_bot.game import GameRunner
from lichess_bot.learning import GameRecord, Learner
from lichess_bot.pacing import MovePacing, NoPacing
from rating.player import MovePlayer
from rating.resign import ResignPolicy

log = logging.getLogger(__name__)


#: Se um desafio aceito não virar partida neste prazo, libera a Luna de novo.
PENDING_TIMEOUT = 60.0


def speed_of(limit: int, increment: int) -> str:
    """Ritmo do Lichess pela duração estimada: base + 40 × incremento."""
    est = limit + 40 * increment
    if est < 29:
        return "ultraBullet"
    if est < 179:
        return "bullet"
    if est < 479:
        return "blitz"
    if est < 1499:
        return "rapid"
    return "classical"


def decline_reason(challenge: dict, cfg: BotConfig, busy: bool) -> Optional[str]:
    """Devolve o motivo de recusa aceito pelo Lichess, ou ``None`` para aceitar."""
    if busy:
        return "later"
    if (challenge.get("variant") or {}).get("key") != "standard":
        return "standard"
    rated = bool(challenge.get("rated"))
    if rated and not cfg.accept_rated:
        return "casual"
    if not rated and not cfg.accept_casual:
        return "rated"
    tc = challenge.get("timeControl") or {}
    if tc.get("type") != "clock":
        return "timeControl"
    if challenge.get("speed") not in cfg.speeds:
        return "timeControl"
    limit, inc = int(tc.get("limit", 0)), int(tc.get("increment", 0))
    if limit + 60 * inc < cfg.min_clock_budget:
        return "tooFast"
    if limit > cfg.max_initial or inc > cfg.max_increment:
        return "tooSlow"
    return None


class LichessBot:
    def __init__(
        self,
        client: LichessClient,
        player_factory: Callable[[], MovePlayer],
        learner: Learner,
        config: BotConfig | None = None,
    ):
        self.client = client
        self.player_factory = player_factory
        self.learner = learner
        self.cfg = config or BotConfig()
        self.games: "queue.Queue[str]" = queue.Queue()
        self.busy = threading.Event()  # partida aceita ou em andamento
        self.playing = threading.Event()
        self._pending_since: Optional[float] = None
        self._seen_games: set[str] = set()
        self.stop = threading.Event()
        self.my_id = ""
        self.my_rating: Optional[int] = None
        self.finished: list[GameRecord] = []

    # ------------------------------------------------------------ eventos
    def handle_event(self, ev: dict) -> None:
        kind = ev.get("type")
        if kind == "challenge":
            ch = ev.get("challenge") or {}
            if (ch.get("challenger") or {}).get("id", "").lower() == self.my_id:
                return  # desafio que nós mesmos enviamos
            reason = decline_reason(ch, self.cfg, self.busy.is_set())
            try:
                if reason:
                    self.client.decline_challenge(ch["id"], reason)
                else:
                    self._mark_pending()
                    self.client.accept_challenge(ch["id"])
            except LichessError as exc:
                log.warning("Falha ao responder desafio %s: %s", ch.get("id"), exc)
                if not reason:
                    self._release()
        elif kind == "gameStart":
            game = ev.get("game") or {}
            game_id = game.get("gameId") or game.get("id")
            if game_id and game_id not in self._seen_games:
                self._seen_games.add(game_id)
                self.busy.set()
                self.games.put(game_id)
        elif kind in ("challengeDeclined", "challengeCanceled"):
            # Desafio que não virou partida: libera, a menos que já esteja jogando.
            if not self.playing.is_set() and self.games.empty():
                self._release()

    def _mark_pending(self) -> None:
        self._pending_since = time.monotonic()
        self.busy.set()

    def _release(self) -> None:
        self._pending_since = None
        self.busy.clear()

    def _expire_pending(self) -> None:
        if (
            self._pending_since is not None
            and not self.playing.is_set()
            and self.games.empty()
            and time.monotonic() - self._pending_since > PENDING_TIMEOUT
        ):
            self._release()

    def _event_loop(self) -> None:
        while not self.stop.is_set():
            try:
                for ev in self.client.stream_events():
                    if self.stop.is_set():
                        return
                    self.handle_event(ev)
            except Exception as exc:  # noqa: BLE001 - reconecta em queda de rede
                log.warning("Stream de eventos caiu (%s); reconectando em 5s.", exc)
                time.sleep(5)

    # ------------------------------------------------------------ partidas
    def play_one(self, game_id: str) -> GameRecord:
        runner = GameRunner(
            self.client,
            self.player_factory(),
            game_id,
            self.my_id,
            pacing=MovePacing() if self.cfg.pacing else NoPacing(),
            resign_policy=ResignPolicy(self.cfg.resign_score, self.cfg.resign_moves),
        )
        record = runner.run()
        if record.luna_rating is not None:
            self.my_rating = record.luna_rating
        self.finished.append(record)
        try:
            self.learner.on_game_finished(record)
        except Exception:  # noqa: BLE001 - aprender não pode derrubar o bot
            log.exception("Aprendiz falhou na partida %s", game_id)
        return record

    def _matchmake(self) -> None:
        bots = [b for b in self.client.online_bots() if b.get("id", "").lower() != self.my_id]
        if self.my_rating is not None:
            w = self.cfg.matchmaking_rating_window
            speed = speed_of(*self.cfg.matchmaking_clock)
            bots = [
                b
                for b in bots
                if abs(
                    ((b.get("perfs") or {}).get(speed) or {}).get("rating", self.my_rating)
                    - self.my_rating
                )
                <= w
            ]
        if not bots:
            return
        target = random.choice(bots)
        limit, inc = self.cfg.matchmaking_clock
        self._mark_pending()
        try:
            self.client.create_challenge(target["id"], limit, inc, rated=self.cfg.accept_rated)
            log.info("Desafio enviado para %s", target["id"])
        except LichessError as exc:
            log.warning("Desafio para %s falhou: %s", target.get("id"), exc)
            self._release()

    def run(self, max_games: Optional[int] = None) -> list[GameRecord]:
        account = self.client.get_account()
        if account.get("title") != "BOT":
            raise SystemExit(
                "Esta conta ainda não é BOT. Veja lichess_bot/GUIA.md (passo de upgrade)."
            )
        self.my_id = account["id"].lower()
        threading.Thread(target=self._event_loop, name="lichess-events", daemon=True).start()
        idle_since = time.monotonic()
        played = 0
        while not self.stop.is_set() and (max_games is None or played < max_games):
            try:
                game_id = self.games.get(timeout=5)
            except queue.Empty:
                self._expire_pending()
                waited = time.monotonic() - idle_since
                if (
                    self.cfg.matchmaking
                    and not self.busy.is_set()
                    and waited >= self.cfg.matchmaking_idle_seconds
                ):
                    self._matchmake()
                    idle_since = time.monotonic()
                continue
            self.playing.set()
            self._pending_since = None
            try:
                rec = self.play_one(game_id)
                log.info("Partida %s terminou: %s (vencedor: %s)", game_id, rec.status, rec.winner)
            except Exception:  # noqa: BLE001 - uma partida com erro não derruba o bot
                log.exception("Erro na partida %s", game_id)
            finally:
                played += 1
                self.playing.clear()
                if self.games.empty():
                    self._release()
                idle_since = time.monotonic()
        self.stop.set()
        return self.finished
