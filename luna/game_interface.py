"""Interface entre a Luna e qualquer motor de regras de xadrez.

A Luna nunca importa um motor diretamente: ela só conversa com um objeto que
segue o protocolo ``GameState``. Hoje o único backend é o adaptador provisório
sobre python-chess (``luna.adapters.python_chess``). Quando o pacote
``chess_engine`` ficar pronto, basta escrever um adaptador novo em
``luna/adapters`` e registrá-lo em ``luna.adapters.BACKENDS``.

Convenções:
- Lances são strings UCI (``"e2e4"``, ``"e7e8q"``).
- Casas são inteiros 0..63 com a1 = 0, b1 = 1, ..., h8 = 63.
- Peças são letras maiúsculas ``P N B R Q K``; a cor vem num booleano à parte
  (``True`` = brancas).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Protocol, runtime_checkable


@dataclass(frozen=True)
class Outcome:
    """Resultado de uma partida terminada."""

    winner: Optional[bool]  # True = brancas, False = pretas, None = empate
    termination: str  # "checkmate", "stalemate", "repetition", "fifty_moves", ...


@runtime_checkable
class GameState(Protocol):
    @property
    def white_to_move(self) -> bool: ...

    @property
    def ply(self) -> int:
        """Número de meios-lances já jogados."""

    def legal_moves(self) -> list[str]: ...

    def push(self, move: str) -> None: ...

    def pop(self) -> str: ...

    def copy(self) -> "GameState": ...

    def is_check(self) -> bool:
        """O lado que vai jogar está em xeque?"""

    def is_checkmate(self) -> bool: ...

    def is_capture(self, move: str) -> bool: ...

    def captured_piece(self, move: str) -> Optional[str]:
        """Letra da peça capturada pelo lance (``"P"`` em en passant) ou None."""

    def moving_piece(self, move: str) -> str: ...

    def is_promotion(self, move: str) -> bool: ...

    def gives_check(self, move: str) -> bool: ...

    def is_repetition(self) -> bool:
        """A posição atual já apareceu antes nesta partida?"""

    def outcome(self, claim_draw: bool = True) -> Optional[Outcome]:
        """Resultado se a partida acabou, senão None."""

    def pieces(self) -> Iterable[tuple[int, str, bool]]:
        """(casa, peça, é_branca) para cada peça no tabuleiro."""

    def mobility(self, white: bool) -> int:
        """Quantidade de casas atacadas pelas peças da cor que não estão
        ocupadas por peças da mesma cor (aproximação pseudo-legal barata)."""

    def fen(self) -> str: ...
