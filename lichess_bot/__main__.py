"""Linha de comando do bot.

    python -m lichess_bot check                 # confere token e se a conta é BOT
    python -m lichess_bot upgrade --confirm     # IRREVERSÍVEL: vira conta BOT
    python -m lichess_bot play --player modulo:fabrica [--learner modulo:fabrica]

O token vem só de LICHESS_BOT_TOKEN. Nada aqui joga sozinho: o comando
``play`` precisa ser executado por você.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from lichess_bot.bot import LichessBot
from lichess_bot.client import DEFAULT_BASE_URL, LichessClient
from lichess_bot.config import BotConfig, read_token
from lichess_bot.learning import JsonlRecorder, LearnerChain
from rating.player import load_factory


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m lichess_bot")
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("check", help="mostra a conta do token e se ela já é BOT")

    up = sub.add_parser("upgrade", help="converte a conta em BOT (irreversível)")
    up.add_argument("--confirm", action="store_true", help="obrigatório: confirma que é irreversível")

    play = sub.add_parser("play", help="espera desafios e joga uma partida por vez")
    play.add_argument("--player", required=True, help="fábrica do jogador, 'modulo:funcao'")
    play.add_argument("--learner", default=None, help="fábrica do aprendiz, recebe data_dir")
    play.add_argument("--data-dir", type=Path, default=Path("lichess_bot/runs"))
    play.add_argument("--max-games", type=int, default=None)
    play.add_argument("--casual-only", action="store_true", help="não aceita partidas valendo rating")
    play.add_argument("--matchmaking", action="store_true", help="desafia outros bots quando ocioso")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    client = LichessClient(read_token(), base_url=args.base_url)

    if args.cmd == "check":
        acc = client.get_account()
        print(f"Conta: {acc.get('username')} | BOT: {'sim' if acc.get('title') == 'BOT' else 'não'}")
        return 0

    if args.cmd == "upgrade":
        if not args.confirm:
            print("O upgrade é irreversível e exige conta sem nenhuma partida. Rode de novo com --confirm.")
            return 2
        print(client.upgrade_to_bot(confirm=True))
        return 0

    cfg = BotConfig(
        accept_rated=not args.casual_only,
        data_dir=args.data_dir,
        matchmaking=args.matchmaking,
    )
    learner = JsonlRecorder(cfg.data_dir)
    if args.learner:
        learner = LearnerChain(learner, load_factory(args.learner)(cfg.data_dir))
    bot = LichessBot(client, load_factory(args.player), learner, cfg)
    bot.run(max_games=args.max_games)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
