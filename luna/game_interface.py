"""Interface entre a Luna e qualquer motor de regras de xadrez.

A Luna nunca importa um motor diretamente: ela só conversa com um objeto que
segue o protocolo ``GameState``. Hoje o único backend é o adaptador provisório
sobre python-chess (``luna.adapters.python_chess``). Quando o pacote
``chess_engine`` ficar pronto, basta escrever um adaptador novo em
``luna/adapters`` e registrá-lo em ``luna.adapters.BACKENDS``.

Convenções:
- Lances são objetos opacos do backend (inteiros, ``chess.Move``...): a Luna só
  os repassa ao próprio backend. ``uci(move)`` e ``parse_uci(texto)`` convertem
  de e para UCI (``"e2e4"``, ``"e7e8q"``) quando é preciso guardar ou exibir.
- Casas são inteiros 0..63 com a1 = 0, b1 = 1, ..., h8 = 63.
- Peças são letras maiúsculas ``P N B R Q K``; a cor vem num booleano à parte
  (``True`` = brancas).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Optional, Protocol, runtime_checkable

Move = Any  # tipo opaco definido por cada backend


@dataclass(frozen=True)
class Outcome:
    """Resultado de uma partida terminada."""

    winner: Optional[bool]  # True = brancas, False = pretas, None = empate
    # Um de: "checkmate", "stalemate", "insufficient_material", "seventyfive_moves",
    # "fivefold_repetition", "fifty_moves", "threefold_repetition".
    termination: str


@runtime_checkable
class GameState(Protocol):
    @property
    def white_to_move(self) -> bool: ...

    @property
    def ply(self) -> int:
        """Número de meios-lances já jogados."""

    def legal_moves(self) -> list[Move]: ...

    def push(self, move: Move) -> None: ...

    def pop(self) -> Move: ...

    def uci(self, move: Move) -> str: ...

    def parse_uci(self, text: str) -> Move: ...

    def san(self, move: Move) -> str:
        """Notação algébrica (SAN) do lance na posição atual, com + ou #."""

    def copy(self) -> "GameState": ...

    def is_check(self) -> bool:
        """O lado que vai jogar está em xeque?"""

    def is_checkmate(self) -> bool: ...

    def is_capture(self, move: Move) -> bool: ...

    def captured_piece(self, move: Move) -> Optional[str]:
        """Letra da peça capturada pelo lance (``"P"`` em en passant) ou None."""

    def moving_piece(self, move: Move) -> str: ...

    def is_promotion(self, move: Move) -> bool: ...

    def gives_check(self, move: Move) -> bool: ...

    def is_repetition(self) -> bool:
        """A posição atual (peças, vez, roques e en passant) já apareceu pelo menos
        uma vez antes nesta partida, contando o histórico anterior à busca?"""

    def outcome(self, claim_draw: bool = True) -> Optional[Outcome]:
        """Resultado se a partida acabou, senão None. Com ``claim_draw`` os empates
        por 50 lances e tripla repetição encerram a partida."""

    def pieces(self) -> Iterable[tuple[int, str, bool]]:
        """(casa, peça, é_branca) para cada peça, em ordem crescente de casa (a1 primeiro).

        A ordem faz parte do contrato: a avaliação soma números de ponto flutuante
        nessa ordem, e ordens diferentes dariam escores diferentes no último dígito,
        o que muda o desempate entre lances e faz os backends jogarem partidas
        diferentes."""

    def mobility(self, white: bool) -> int:
        """Soma, para cavalos, bispos, torres e damas da cor (peões e rei ficam de
        fora), das casas que cada peça ataca e não estão ocupadas por peça da
        mesma cor. Ignora cravadas: é uma aproximação pseudo-legal barata."""

    def fen(self) -> str: ...
