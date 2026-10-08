import json

import pytest

from lichess_bot.bot import LichessBot, decline_reason, speed_of
from lichess_bot.client import LichessClient, LichessError
from lichess_bot.config import BotConfig
from lichess_bot.game import GameRunner
from lichess_bot.learning import JsonlRecorder, build_record, load_records
from rating.player import FunctionPlayer


# ------------------------------------------------------------------ fakes
class FakeResponse:
    def __init__(self, status=200, body=None, lines=None):
        self.status_code = status
        self._body = body
        self._lines = lines or []
        self.text = json.dumps(body) if body is not None else ""
        self.content = self.text.encode()

    def json(self):
        return self._body

    def iter_lines(self):
        yield from self._lines

    def close(self):
        pass


class FakeSession:
    def __init__(self, responses):
        self.headers = {}
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kw):
        self.calls.append((method, url, kw))
        return self.responses.pop(0)

    def get(self, url, **kw):
        self.calls.append(("GET", url, kw))
        return self.responses.pop(0)


class FakeClient:
    """Cliente falso que simula o Lichess respondendo aos lances."""

    def __init__(self, game_events):
        self.game_events = game_events
        self.moves = []
        self.declined = []
        self.accepted = []
        self.claimed = []

    def stream_game(self, game_id):
        yield from self.game_events

    def make_move(self, game_id, move):
        self.moves.append(move)

    def accept_challenge(self, cid):
        self.accepted.append(cid)

    def decline_challenge(self, cid, reason):
        self.declined.append((cid, reason))

    def resign(self, game_id):
        pass

    def claim_victory(self, game_id):
        self.claimed.append(game_id)


def full(moves="", status="started", white="luna", black="opp", winner=None):
    st = {
        "type": "gameState",
        "moves": moves,
        "status": status,
        "wtime": 60000,
        "btime": 60000,
        "winc": 0,
        "binc": 0,
    }
    if winner:
        st["winner"] = winner
    return {
        "type": "gameFull",
        "id": "g1",
        "variant": {"key": "standard"},
        "speed": "blitz",
        "rated": True,
        "white": {"id": white, "name": white.title(), "rating": 1500},
        "black": {"id": black, "name": black.title(), "rating": 1600},
        "initialFen": "startpos",
        "state": st,
    }


def challenge(**over):
    ch = {
        "id": "c1",
        "challenger": {"id": "someone"},
        "variant": {"key": "standard"},
        "rated": True,
        "speed": "classical",
        "timeControl": {"type": "clock", "limit": 1800, "increment": 20},
    }
    ch.update(over)
    return ch


# --------------------------------------------------------------- cliente
def test_client_sends_bearer_and_retries_429():
    sleeps = []
    s = FakeSession([FakeResponse(429), FakeResponse(200, {"id": "luna", "title": "BOT"})])
    c = LichessClient("tok", session=s, sleep=sleeps.append)
    assert c.is_bot_account()
    assert s.headers["Authorization"] == "Bearer tok"
    assert sleeps == [60.0]


def test_client_raises_on_error():
    c = LichessClient("tok", session=FakeSession([FakeResponse(400, {"error": "x"})]))
    with pytest.raises(LichessError):
        c.make_move("g", "e2e4")


def test_stream_skips_keepalive_lines():
    lines = [b"", b'{"type":"gameStart","game":{"gameId":"a"}}', b""]
    c = LichessClient("tok", session=FakeSession([FakeResponse(200, lines=lines)]))
    assert list(c.stream_events()) == [{"type": "gameStart", "game": {"gameId": "a"}}]


def test_upgrade_requires_confirmation():
    c = LichessClient("tok", session=FakeSession([]))
    with pytest.raises(PermissionError):
        c.upgrade_to_bot()


def test_empty_token_rejected():
    with pytest.raises(ValueError):
        LichessClient("")


# --------------------------------------------------------------- desafios
@pytest.mark.parametrize(
    "over,busy,expected",
    [
        ({}, False, None),
        ({}, True, "later"),
        ({"variant": {"key": "chess960"}}, False, "standard"),
        ({"timeControl": {"type": "unlimited"}}, False, "timeControl"),
        ({"timeControl": {"type": "clock", "limit": 600, "increment": 5}}, False, "tooFast"),
        (
            {"speed": "rapid", "timeControl": {"type": "clock", "limit": 900, "increment": 10}},
            False,
            None,
        ),
        (
            {"speed": "rapid", "timeControl": {"type": "clock", "limit": 1500, "increment": 0}},
            False,
            None,
        ),
        (
            {"speed": "blitz", "timeControl": {"type": "clock", "limit": 300, "increment": 3}},
            False,
            "timeControl",
        ),
        ({"timeControl": {"type": "clock", "limit": 20000, "increment": 0}}, False, "tooSlow"),
        ({"speed": "correspondence"}, False, "timeControl"),
    ],
)
def test_decline_reason(over, busy, expected):
    assert decline_reason(challenge(**over), BotConfig(), busy) == expected


def test_casual_only_declines_rated():
    assert decline_reason(challenge(), BotConfig(accept_rated=False), False) == "casual"


def test_speed_of_matches_lichess_rule():
    assert speed_of(60, 0) == "bullet"
    assert speed_of(300, 3) == "blitz"
    assert speed_of(600, 5) == "rapid"
    assert speed_of(1800, 20) == "classical"


def test_bot_accepts_one_and_declines_while_busy(tmp_path):
    client = FakeClient([])
    bot = LichessBot(client, lambda: None, JsonlRecorder(tmp_path))
    bot.handle_event({"type": "challenge", "challenge": challenge(id="a")})
    bot.handle_event({"type": "challenge", "challenge": challenge(id="b")})
    assert client.accepted == ["a"]
    assert client.declined == [("b", "later")]
    bot.handle_event({"type": "gameStart", "game": {"gameId": "g1"}})
    bot.handle_event({"type": "gameStart", "game": {"gameId": "g1"}})  # duplicado
    assert bot.games.qsize() == 1


def test_canceled_challenge_frees_the_bot(tmp_path):
    client = FakeClient([])
    bot = LichessBot(client, lambda: None, JsonlRecorder(tmp_path))
    bot.handle_event({"type": "challenge", "challenge": challenge(id="a")})
    bot.handle_event({"type": "challengeCanceled", "challenge": {"id": "a"}})
    bot.handle_event({"type": "challenge", "challenge": challenge(id="b")})
    assert client.accepted == ["a", "b"]


# ---------------------------------------------------------------- partida
def test_runner_plays_on_its_turn_and_records_mate(tmp_path):
    events = [
        full(""),
        {"type": "gameState", "moves": "f2f3", "status": "started"},
        {"type": "gameState", "moves": "f2f3 e7e5", "status": "started"},
        {"type": "gameState", "moves": "f2f3 e7e5 g2g4", "status": "started"},
        {"type": "gameState", "moves": "f2f3 e7e5 g2g4 d8h4", "status": "mate", "winner": "black"},
    ]
    client = FakeClient(events)
    script = iter(["f2f3", "g2g4"])
    player = FunctionPlayer(lambda fen, legal: next(script))
    rec = GameRunner(client, player, "g1", "luna").run()
    assert client.moves == ["f2f3", "g2g4"]  # só joga na própria vez
    assert rec.luna_color == "white" and rec.winner == "black"
    assert rec.luna_score == 0.0
    assert rec.checks_by_opponent == 1 and rec.checks_by_luna == 0
    assert rec.opponent == "Opp" and rec.opponent_rating == 1600

    JsonlRecorder(tmp_path).on_game_finished(rec)
    loaded = load_records(tmp_path)
    assert loaded[0].game_id == "g1" and loaded[0].moves == rec.moves
    assert (tmp_path / "games.pgn").read_text().count("[Event") == 1


def test_runner_as_black_and_illegal_move_fallback():
    events = [
        full("", white="opp", black="luna"),
        {"type": "gameState", "moves": "e2e4", "status": "started"},
        {"type": "gameState", "moves": "e2e4 a7a6", "status": "resign", "winner": "black"},
    ]
    client = FakeClient(events)
    player = FunctionPlayer(lambda fen, legal: "zzzz")
    rec = GameRunner(client, player, "g1", "luna").run()
    assert len(client.moves) == 1 and client.moves[0] != "zzzz"
    assert rec.luna_color == "black" and rec.luna_score == 1.0


def test_runner_claims_victory_when_opponent_gone():
    events = [
        full("e2e4", white="opp", black="luna"),
        {"type": "opponentGone", "gone": True, "claimWinInSeconds": 0},
        {"type": "gameState", "moves": "e2e4 e7e5", "status": "timeout", "winner": "black"},
    ]
    client = FakeClient(events)
    GameRunner(client, FunctionPlayer(lambda fen, legal: "e7e5"), "g1", "luna").run()
    assert client.claimed == ["g1"]


def test_build_record_counts_luna_moves():
    rec = build_record("x", "black", ["f2f3", "e7e5", "g2g4", "d8h4"], "mate", "black")
    assert rec.luna_moves == 2 and rec.checks_by_luna == 1 and rec.luna_won_by_mate
