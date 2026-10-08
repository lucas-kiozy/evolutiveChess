"""Critério de desistência da Luna, igual no rating, no Lichess e no tabuleiro.

Regra (o padrão do lichess-bot: ``resign_score: -1000``, ``resign_moves: 3``):
a Luna desiste quando a avaliação da raiz da busca, do ponto de vista dela, fica
em -1000 centipeões ou menos (ou é mate contra ela) por 3 lances seguidos dela.
Exigir lances seguidos evita desistir no meio de uma troca.

Decisão do Lucas: a Luna **só desiste se não enxergar nenhuma possibilidade de
empate forçado**. Antes de desistir, ``forced_draw_available`` procura, a
partir da posição real (com o histórico, para contar repetições), um caminho
que ela consiga impor até o empate: afogamento, material insuficiente,
repetição tripla, regra dos 50 lances ou xeque perpétuo, em até
``DRAW_SEARCH_PLIES`` meios-lances. Também não desiste se o adversário não
tiver material para dar mate, nem se o próprio jogador disser que vê empate
(``player.sees_forced_draw()``). Se a busca estourar o limite de nós sem
conclusão, ela continua jogando.

De onde vem a avaliação:

1. ``player.should_resign(fen)``, se o jogador decidir sozinho;
2. ``player.last_score``: escore em centipeões do último ``choose_move``, do
   ponto de vista de quem escolheu o lance;
3. sem nenhum dos dois, o material (P=1, N=3, B=3, R=5, Q=9) × 100 depois do
   lance escolhido, como aproximação: 10 pontos atrás ≈ -1000 cp.

No placar, uma desistência vale como qualquer vitória: 1 ponto para quem não
desistiu, 0 para quem desistiu, como no Lichess.
"""

from __future__ import annotations

from typing import Optional

import chess

RESIGN_SCORE = -1000  # centipeões
RESIGN_MOVES = 3
#: Profundidade da busca de empate forçado: 8 meios-lances bastam para um xeque
#: perpétuo simples repetir a posição três vezes.
DRAW_SEARCH_PLIES = 8
DRAW_SEARCH_NODES = 20_000

PIECE_VALUES = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
}


def material_balance(board: chess.Board, color: chess.Color) -> int:
    """Material de ``color`` menos o do adversário, em pontos."""
    total = 0
    for piece_type, value in PIECE_VALUES.items():
        total += value * len(board.pieces(piece_type, color))
        total -= value * len(board.pieces(piece_type, not color))
    return total


class ResignPolicy:
    """Conta lances seguidos com avaliação ≤ ``score`` e diz quando desistir."""

    def __init__(self, score: float = RESIGN_SCORE, moves: int = RESIGN_MOVES):
        if score >= 0 or moves <= 0:
            raise ValueError("score precisa ser negativo e moves positivo")
        self.score = score
        self.moves = moves
        self._streak = 0

    def new_game(self) -> None:
        self._streak = 0

    def update(self, score_cp: float) -> bool:
        """Registra a avaliação de um lance da Luna; True = desistir agora."""
        self._streak = self._streak + 1 if score_cp <= self.score else 0
        return self._streak >= self.moves


class _Budget(Exception):
    pass


def _drawn(board: chess.Board) -> bool:
    """Empate já garantido na posição (inclui os que podem ser reivindicados)."""
    return (
        board.is_stalemate()
        or board.is_insufficient_material()
        or board.halfmove_clock >= 100
        or board.is_repetition(3)
    )


def forced_draw_available(
    board: chess.Board,
    max_plies: int = DRAW_SEARCH_PLIES,
    max_nodes: int = DRAW_SEARCH_NODES,
) -> bool:
    """O lado que vai jogar consegue forçar empate (ou melhor) em ``max_plies``?

    Busca E-OU: nos lances de quem procura o empate, basta um caminho; nos do
    adversário, todas as respostas precisam terminar em empate. Do lado de quem
    procura, entram só lances que dão xeque ou que empatam (ou matam) na hora,
    que é o que cobre afogamento, material insuficiente, repetição, 50 lances e
    xeque perpétuo sem explodir o custo. Sem conclusão dentro de ``max_nodes``,
    devolve True: na dúvida, não desiste.
    """
    board = board.copy(stack=True)
    nodes = [0]

    def tick() -> None:
        nodes[0] += 1
        if nodes[0] > max_nodes:
            raise _Budget

    def ours(depth: int) -> bool:
        if depth <= 0:
            return False
        for move in list(board.legal_moves):
            tick()
            check = board.gives_check(move)
            board.push(move)
            try:
                if board.is_checkmate() or _drawn(board):
                    return True
                if check and theirs(depth - 1):
                    return True
            finally:
                board.pop()
        return False

    def theirs(depth: int) -> bool:
        if depth <= 0:
            return False
        for move in list(board.legal_moves):
            tick()
            board.push(move)
            try:
                if board.is_checkmate():
                    return False
                if not _drawn(board) and not ours(depth - 1):
                    return False
            finally:
                board.pop()
        return True

    if _drawn(board) or board.has_insufficient_material(not board.turn):
        return True  # o adversário nem tem material para dar mate
    try:
        return ours(max_plies)
    except _Budget:
        return True


def score_after(player: object, fen: str, move_uci: str) -> float:
    """Avaliação (cp) do lance escolhido, do ponto de vista de quem o escolheu."""
    score = getattr(player, "last_score", None)
    if isinstance(score, (int, float)):
        return float(score)
    board = chess.Board(fen)
    side = board.turn
    board.push_uci(move_uci)
    return 100.0 * material_balance(board, side)


def wants_to_resign(
    player: object, policy: Optional[ResignPolicy], board: chess.Board, move_uci: str
) -> bool:
    """Chame depois de ``choose_move`` e antes de jogar o lance escolhido.

    ``board`` é a posição antes do lance, com o histórico da partida.
    """
    own = getattr(player, "should_resign", None)
    if callable(own):
        return bool(own(board.fen()))
    if policy is None:
        return False
    if not policy.update(score_after(player, board.fen(), move_uci)):
        return False
    sees_draw = getattr(player, "sees_forced_draw", None)  # LunaPlayer, PR #16
    if callable(sees_draw) and sees_draw():
        return False
    return not forced_draw_available(board)
