"""Cliente mínimo da Bot API oficial do Lichess (https://lichess.org/api#tag/Bot).

Regras da própria documentação que este cliente respeita:
* Só uma requisição comum por vez (um ``Lock`` serializa as chamadas; os dois
  streams de longa duração, eventos e partida, são a exceção prevista).
* Ao receber HTTP 429, espera um minuto inteiro antes de tentar de novo.
* O token vem do ambiente e nunca é gravado em disco nem registrado em log.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any, Callable, Iterator, Optional

import requests

log = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://lichess.org"
RATE_LIMIT_WAIT = 60.0


class LichessError(RuntimeError):
    def __init__(self, status: int, message: str):
        super().__init__(f"HTTP {status}: {message}")
        self.status = status


class LichessClient:
    def __init__(
        self,
        token: str,
        base_url: str = DEFAULT_BASE_URL,
        session: Optional[requests.Session] = None,
        sleep: Callable[[float], None] = time.sleep,
        timeout: float = 30.0,
    ):
        if not token:
            raise ValueError("Token do Lichess ausente (defina LICHESS_BOT_TOKEN).")
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "User-Agent": "evolutiveChess-Luna-bot (github.com/lucas-kiozy/evolutiveChess)",
            }
        )
        self._lock = threading.Lock()
        self._sleep = sleep
        self.timeout = timeout

    # ------------------------------------------------------------------ base
    def _request(self, method: str, path: str, retries: int = 3, **kw: Any) -> Any:
        url = f"{self.base_url}{path}"
        for attempt in range(retries + 1):
            with self._lock:
                resp = self.session.request(method, url, timeout=self.timeout, **kw)
            if resp.status_code == 429 and attempt < retries:
                log.warning(
                    "Lichess pediu para ir mais devagar (429); aguardando %ss", RATE_LIMIT_WAIT
                )
                self._sleep(RATE_LIMIT_WAIT)
                continue
            if resp.status_code >= 400:
                raise LichessError(resp.status_code, resp.text[:300])
            if not resp.content:
                return None
            try:
                return resp.json()
            except ValueError:
                return resp.text
        raise LichessError(429, "limite de requisições persistente")

    def _stream(self, path: str) -> Iterator[dict]:
        """Lê um endpoint ND-JSON; linhas vazias são keep-alive e são ignoradas."""
        url = f"{self.base_url}{path}"
        while True:
            resp = self.session.get(url, stream=True, timeout=(self.timeout, None))
            if resp.status_code == 429:
                resp.close()
                self._sleep(RATE_LIMIT_WAIT)
                continue
            if resp.status_code >= 400:
                text = resp.text[:300]
                resp.close()
                raise LichessError(resp.status_code, text)
            break
        try:
            for raw in resp.iter_lines():
                if not raw:
                    continue
                yield json.loads(raw)
        finally:
            resp.close()

    # --------------------------------------------------------------- account
    def get_account(self) -> dict:
        return self._request("GET", "/api/account")

    def is_bot_account(self) -> bool:
        return (self.get_account() or {}).get("title") == "BOT"

    def upgrade_to_bot(self, confirm: bool = False) -> Any:
        """Converte a conta em BOT. IRREVERSÍVEL e só funciona em conta sem partidas.

        Exige ``confirm=True`` de propósito, para nunca acontecer por engano.
        """
        if not confirm:
            raise PermissionError("upgrade_to_bot é irreversível; chame com confirm=True.")
        return self._request("POST", "/api/bot/account/upgrade")

    # --------------------------------------------------------------- streams
    def stream_events(self) -> Iterator[dict]:
        return self._stream("/api/stream/event")

    def stream_game(self, game_id: str) -> Iterator[dict]:
        return self._stream(f"/api/bot/game/stream/{game_id}")

    # ------------------------------------------------------------ challenges
    def accept_challenge(self, challenge_id: str) -> Any:
        return self._request("POST", f"/api/challenge/{challenge_id}/accept")

    def decline_challenge(self, challenge_id: str, reason: str = "generic") -> Any:
        return self._request(
            "POST", f"/api/challenge/{challenge_id}/decline", data={"reason": reason}
        )

    def create_challenge(
        self,
        username: str,
        clock_limit: int,
        clock_increment: int,
        rated: bool = True,
        color: str = "random",
    ) -> Any:
        data = {
            "rated": str(rated).lower(),
            "clock.limit": clock_limit,
            "clock.increment": clock_increment,
            "color": color,
            "variant": "standard",
        }
        return self._request("POST", f"/api/challenge/{username}", data=data)

    def online_bots(self, limit: int = 50) -> list[dict]:
        """Lista bots online (ND-JSON). Usada só pelo matchmaking opcional."""
        resp = None
        with self._lock:
            resp = self.session.get(
                f"{self.base_url}/api/bot/online", params={"nb": limit}, timeout=self.timeout
            )
        if resp.status_code >= 400:
            raise LichessError(resp.status_code, resp.text[:300])
        return [json.loads(line) for line in resp.text.splitlines() if line.strip()]

    # ----------------------------------------------------------------- games
    def make_move(self, game_id: str, move: str) -> Any:
        return self._request("POST", f"/api/bot/game/{game_id}/move/{move}")

    def resign(self, game_id: str) -> Any:
        return self._request("POST", f"/api/bot/game/{game_id}/resign")

    def abort(self, game_id: str) -> Any:
        return self._request("POST", f"/api/bot/game/{game_id}/abort")

    def claim_victory(self, game_id: str) -> Any:
        return self._request("POST", f"/api/bot/game/{game_id}/claim-victory")
