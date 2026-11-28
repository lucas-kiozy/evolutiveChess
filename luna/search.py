"""Busca alfa-beta (negamax) com quiescência sobre capturas.

Mates são pontuados como ``MATE_SCORE - ply``, então entre dois mates a busca
prefere o mais curto, o que está alinhado com o critério de aptidão (mate em menos
lances).

A profundidade e o ruído vêm de ``SearchConfig``. A profundidade da quiescência, o
contempt e as extensões em xeque são genes (``luna.genome``) e evoluem junto com a
avaliação; ``SearchConfig`` só os sobrepõe quando recebe um valor explícito.

Limite de tempo (``SearchConfig.time_limit``, pedido do Lucas em 2026-11-02): a
busca passa a ser por aprofundamento iterativo, profundidade 1, 2, ... até a pedida,
com o melhor lance da camada anterior buscado primeiro. Quando o tempo acaba, ela
joga o melhor lance da última camada completa, ou o da camada interrompida se ele
já superou aquele (o primeiro lance buscado nela é justamente o anterior). As
camadas rasas custam pouco perto da última (Korf 1985, *Artificial Intelligence*
27:97-109) e melhoram a ordem dos lances da seguinte (Slate & Atkin 1977, Chess 4.5).
Sem ``time_limit`` a busca vai direto à profundidade pedida, como antes.

Limite de nós (``SearchConfig.node_limit``, recomendação da revisão do AG de
2026-11-28 aprovada pelo Lucas): o mesmo aprofundamento iterativo, mas o lance acaba
quando a busca visita ``node_limit`` nós, e não quando o relógio passa. O resultado
deixa de depender da velocidade e da carga da máquina, e a mesma semente reproduz a
mesma partida. É o que o treino usa a partir do treino-v5: com o relógio, genes que
deixam a busca mais lenta (quiescência, extensão em xeque) eram julgados também pela
CPU (Jin e Branke 2005, IEEE Trans. Evol. Comput. 9(3):303-317, sobre aptidão que
muda com o tempo). Com os dois limites, vale o que acabar primeiro.

Heurísticas de busca (``SearchConfig.heuristics``, ligadas por padrão; recomendação
aprovada pelo Lucas em 2026-11-17 de tratar a busca como alavanca de força):

- Tabela de transposição: guarda, por posição, a profundidade, o escore (exato ou
  limite) e o melhor lance, para não buscar de novo a mesma posição e para buscar o
  melhor lance primeiro na camada seguinte (Greenblatt, Eastlake & Crocker 1967;
  Marsland 1986, *ICCA Journal* 9(1):3-19). É limpa a cada lance da partida, porque o
  escore de empate depende de quem está na raiz.
- Lances killer: lances quietos que causaram corte na mesma distância da raiz vêm logo
  depois das capturas (Akl & Newborn 1977).
- Heurística history: os outros lances quietos são ordenados por quantos cortes já
  causaram, pesados por profundidade² (Schaeffer 1989, *IEEE TPAMI* 11(11):1203-1212,
  que mediu a history e a tabela de transposição como as que mais reduzem a árvore).

Nenhuma delas muda o valor minimax: só a ordem e o que deixa de ser buscado de novo.

Orçamento de tempo (``SearchConfig.budget``, pedido do Lucas em 2026-11-27): nas
partidas oficiais, em vez de um limite fixo, a busca administra o tempo de cada lance
dentro de uma regra por partida, "pelo menos 30 de 35 lances em até 20 s":

- **Teto normal** (``TimeBudget.move_time``, 20 s): nenhum lance comum passa disso.
- **Só começa uma camada que cabe**: o tempo da próxima camada é previsto pelo fator
  de ramificação efetivo das duas últimas (tempo da última x razão entre elas); se ela
  não cabe no teto, a busca para ali em vez de começar e jogar fora a camada.
- **Parada antecipada**: se o melhor lance foi o mesmo nas últimas
  ``stable_depths`` camadas, sem queda de avaliação, a próxima camada só começa se
  terminar até ``stable_fraction`` do teto. É a ideia da "estabilidade do melhor
  lance" que os motores usam para economizar tempo em lances óbvios (Hyatt 1984,
  *ICCA Journal* 7(1):4-23; Šolak e Vučković 2009, *Computer Science and Information
  Systems* 6(2):157-176, que testaram regras desse tipo em partidas).
- **Extensão**: passar do teto só é permitido quando a busca está instável, isto é,
  o melhor lance mudou entre as duas últimas camadas, a avaliação caiu
  ``drop_cp`` centipeões ou mais, ou, na camada em andamento, outro lance passou à
  frente do anterior. Aí o teto sobe até ``extended_time`` (40 s). Cada lance que
  passa de ``move_time`` gasta um crédito; com ``max_extensions`` (5) créditos usados
  na partida, o teto volta a ser fixo até o fim.
- **Lance único**: com só um lance legal, ele é jogado depois da camada 1.
- **Relógio** (``Searcher.clock``): quando há relógio de verdade, como no Lichess, os
  tetos encolhem para caber no tempo restante (restante / 25 + 3/4 do incremento, e
  no máximo 1/8 do restante na extensão).

A escala de profundidade continua sendo o mínimo de cada lance: as camadas até ela
sempre começam, e só o teto de tempo as interrompe.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Optional

from luna.evaluation import MATE_SCORE, evaluate
from luna.game_interface import GameState, Move
from luna.genome import Genome

_ORDER_VALUE = {"P": 1, "N": 3, "B": 3, "R": 5, "Q": 9, "K": 0}
_EXACT, _LOWER, _UPPER = 0, 1, 2  # tipo do escore guardado na tabela de transposição
_TT_MAX = 500_000  # posições na tabela antes de esvaziá-la
EXTRA_START_FRACTION = 0.25  # camada além da escala só começa antes deste tanto do limite
INF = float("inf")
MAX_PLY = 1000  # escores acima de MATE_SCORE - MAX_PLY são mates
#: Segundos por lance em todas as partidas da Luna, treino e oficiais (decisão do
#: Lucas em 2026-11-02).
MOVE_TIME_LIMIT = 14.0
_CLOCK_EVERY = 256  # nós entre consultas ao relógio


class _Timeout(Exception):
    pass


@dataclass
class TimeBudget:
    """Gestão de tempo por partida (pedido do Lucas em 2026-11-27); ver o topo do módulo."""

    move_time: float = 20.0  # teto normal por lance, em segundos
    extended_time: float = 40.0  # teto absoluto de um lance estendido
    max_extensions: int = 5  # lances por partida que podem passar de move_time
    stable_depths: int = 3  # camadas seguidas com o mesmo melhor lance = lance estável
    stable_fraction: float = 0.4  # com lance estável, a próxima camada tem que caber nisto
    drop_cp: float = 50.0  # queda de avaliação entre camadas que conta como instabilidade
    unstable_from_depth: int = 4  # mudanças em camadas mais rasas não contam
    safety: float = 0.2  # margem antes do teto, para o lance sair antes dele

    @classmethod
    def from_dict(cls, d: dict) -> "TimeBudget":
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})


@dataclass
class SearchConfig:
    depth: int = 2
    noise: float = 0.0  # ruído uniforme (centipeões) na raiz, para variar partidas
    # None = usa o gene do genoma. Um número sobrepõe o gene (testes, experimentos).
    quiescence_depth: Optional[int] = None  # 0 desliga a quiescência
    # "Contempt": quanto um empate (repetição ou afogamento) vale de menos para quem
    # está buscando. Em autojogo os dois lados querem dar mate, então os dois evitam
    # repetir posições em vez de ficar indo e voltando até a tripla repetição.
    contempt: Optional[float] = None
    # Janela mais funda: do lance ``deep_from_move`` ao ``deep_to_move`` (contados como
    # no xadrez, um lance = brancas e pretas) a busca usa ``deep_depth`` em vez de
    # ``depth``. None desliga. No treino o padrão é 3 nos lances 8 a 12, pedido do
    # Lucas para ganhar força no meio-jogo sem pagar a profundidade 3 inteira.
    deep_depth: Optional[int] = None
    deep_from_move: int = 8
    deep_to_move: int = 12
    # Escala por lance: ((a partir do lance, profundidade), ...) em ordem crescente.
    # Se existir, manda sobre ``depth`` e a janela funda. Nas partidas oficiais é
    # ``luna.promotion.OFFICIAL_SCHEDULE``.
    schedule: Optional[tuple[tuple[int, int], ...]] = None
    # Segundos por lance. None = sem limite (a busca vai direto à profundidade).
    time_limit: Optional[float] = None
    # Tabela de transposição + killer + history. False = busca anterior (para comparar).
    heuristics: bool = True
    # Com ``time_limit``: meios-lances a mais que a busca pode ir além da escala enquanto
    # sobra tempo. Uma camada extra só começa se o lance gastou menos de
    # ``EXTRA_START_FRACTION`` do limite, porque cada camada custa várias vezes a anterior.
    extra_depth: int = 0
    # Orçamento de tempo por partida. Se existir, manda sobre ``time_limit``.
    budget: Optional[TimeBudget] = None
    # Nós por lance (aprofundamento iterativo, como ``time_limit``). None = sem limite.
    # Com ``extra_depth``, uma camada além da escala só começa se o lance gastou menos
    # de ``EXTRA_START_FRACTION`` dos nós.
    node_limit: Optional[int] = None

    @classmethod
    def from_dict(cls, d: dict) -> "SearchConfig":
        keys = (
            "depth",
            "noise",
            "quiescence_depth",
            "contempt",
            "deep_depth",
            "deep_from_move",
            "deep_to_move",
            "schedule",
            "time_limit",
            "heuristics",
            "extra_depth",
            "budget",
            "node_limit",
        )
        kwargs = {k: d[k] for k in keys if k in d}
        if isinstance(kwargs.get("budget"), dict):
            kwargs["budget"] = TimeBudget.from_dict(kwargs["budget"])
        if kwargs.get("schedule") is not None:
            kwargs["schedule"] = tuple((int(m), int(dp)) for m, dp in kwargs["schedule"])
        return cls(**kwargs)

    def depth_at(self, ply: int) -> int:
        """Profundidade para o meio-lance ``ply`` (0 = primeiro lance das brancas)."""
        return self.depth_for_move(ply // 2 + 1)

    def depth_for_move(self, move: int) -> int:
        """Profundidade para o lance ``move`` (contado como no xadrez, a partir de 1)."""
        if self.schedule:
            depth = self.schedule[0][1]
            for start, d in self.schedule:
                if move >= start:
                    depth = d
            return depth
        if self.deep_depth and self.deep_from_move <= move <= self.deep_to_move:
            return self.deep_depth
        return self.depth


def _move_number(state: GameState) -> int:
    """Número do lance da posição, do campo da FEN: vale também para partidas que
    começam de uma FEN, em que alguns backends contam ``ply`` a partir de 0."""
    try:
        return max(1, int(state.fen().split()[5]))
    except (IndexError, ValueError):
        return state.ply // 2 + 1


class Searcher:
    def __init__(self, genome: Genome, config: SearchConfig, rng: Optional[random.Random] = None):
        self.genome = genome
        self.config = config
        self.rng = rng or random.Random()
        self.nodes = 0
        # Escore real (sem o ruído) do lance escolhido na última busca, em centipeões e
        # do ponto de vista de quem jogou; mates valem perto de ±MATE_SCORE.
        self.last_score: Optional[float] = None
        g = genome.genes
        q = config.quiescence_depth
        self.quiescence_depth = int(g["quiescence_depth"] if q is None else q)
        self.contempt = g["contempt"] if config.contempt is None else config.contempt
        self.check_extensions = int(g["check_extension"])
        self._deadline: Optional[float] = None
        self._node_cap: Optional[int] = None  # nós absolutos em que o lance acaba
        self._tt: dict = {}
        self._killers: dict[int, list] = {}
        self._history: dict = {}
        # Orçamento de tempo: créditos gastos na partida, relógio e estatísticas do lance.
        self.extensions_used = 0
        self.clock: Optional[tuple[float, float]] = None  # (restante, incremento) em s
        self.last_info: dict = {}
        self._extend_to: Optional[float] = None
        self._unstable = False
        self._prev_iter_score: Optional[float] = None

    def new_game(self) -> None:
        """Zera os créditos de extensão e o relógio (uma partida nova começa)."""
        self.extensions_used = 0
        self.clock = None

    def choose_move(self, state: GameState) -> Optional[Move]:
        # Ordem UCI antes da ordenação por capturas: desempates e ruído ficam iguais
        # em qualquer backend, independente da ordem em que ele gera os lances.
        moves = self._ordered(state, sorted(state.legal_moves(), key=state.uci))
        if not moves:
            return None
        depth = self.config.depth_for_move(_move_number(state))
        self._tt, self._killers, self._history = {}, {}, {}
        if self.config.budget is not None:
            return self._choose_budgeted(state, moves, depth)
        limit = self.config.time_limit
        node_limit = self.config.node_limit
        if not limit and not node_limit:
            best_move, self.last_score, _ = self._root(state, moves, depth)
            return best_move
        deadline = time.monotonic() + limit if limit else None
        node_cap = self.nodes + node_limit if node_limit else None
        best_move, best_real = moves[0], 0.0
        start = state.ply
        try:
            for d in range(1, depth + self.config.extra_depth + 1):
                if d > depth and not self._room_for_extra(deadline, limit, node_cap):
                    break  # camada além da escala: só se ainda sobra bastante tempo/nós
                # A camada 1 sempre termina (custa milissegundos): garante um lance e
                # um escore para a regra de desistência.
                self._deadline = deadline if d > 1 else None
                self._node_cap = node_cap if d > 1 else None
                best_move, best_real, _ = self._root(state, moves, d)
                moves = [best_move] + [m for m in moves if m != best_move]
                if abs(best_real) >= MATE_SCORE - MAX_PLY:
                    break  # mate achado: mais fundo não muda o lance
        except _Timeout as stop:
            while state.ply > start:  # desfaz os lances que a busca deixou no meio
                state.pop()
            partial = stop.args[0] if stop.args else None
            if partial is not None:  # a camada interrompida já achou algo
                best_move, best_real = partial
        finally:
            self._deadline = None
            self._node_cap = None
        self.last_score = best_real
        return best_move

    def _room_for_extra(
        self, deadline: Optional[float], limit: Optional[float], node_cap: Optional[int]
    ) -> bool:
        """Uma camada além da escala só começa se sobra mais que 1 - EXTRA_START_FRACTION
        do tempo e dos nós do lance."""
        keep = 1 - EXTRA_START_FRACTION
        if deadline is not None and time.monotonic() > deadline - limit * keep:
            return False
        node_limit = self.config.node_limit
        if node_cap is not None and self.nodes > node_cap - node_limit * keep:
            return False
        return True

    def caps(self) -> tuple[float, float]:
        """(teto normal, teto estendido) do próximo lance, já com o relógio, se houver."""
        b = self.config.budget
        cap, ext = b.move_time, max(b.move_time, b.extended_time)
        if self.clock is not None:
            remaining, inc = self.clock
            cap = min(cap, max(0.3, remaining / 25 + 0.75 * inc))
            ext = min(ext, max(cap, remaining / 8))
        return cap, ext

    def _choose_budgeted(self, state: GameState, moves: list[Move], min_depth: int) -> Move:
        b = self.config.budget
        cap, ext = self.caps()
        t0 = time.monotonic()
        nodes0 = self.nodes
        can_extend = self.extensions_used < b.max_extensions and ext > cap
        max_depth = min_depth + self.config.extra_depth
        best_move, best_real = moves[0], 0.0
        done: list[tuple[int, Move, float, float]] = []  # (camada, lance, escore, segundos)
        reason = "profundidade máxima"
        start = state.ply
        self._unstable = False
        self._prev_iter_score = None
        try:
            for d in range(1, max_depth + 1):
                elapsed = time.monotonic() - t0
                if d > 1 and len(moves) == 1:
                    reason = "lance único"
                    break
                if d > min_depth and len(done) >= 2:
                    last, before = done[-1][3], done[-2][3]
                    factor = min(8.0, max(1.5, last / before)) if before > 1e-3 else 4.0
                    finish = elapsed + last * factor
                    if self._unstable and can_extend:
                        room, why = ext, "não cabe no teto estendido"
                    elif self._stable(done):
                        room, why = cap * b.stable_fraction, "lance estável"
                    else:
                        room, why = cap, "próxima camada não cabe no teto"
                    if finish > room - b.safety:
                        reason = why
                        break
                # A camada 1 sempre termina (custa milissegundos): garante um lance e
                # um escore para a regra de desistência.
                if d > 1:
                    self._deadline = t0 + cap - b.safety
                    self._extend_to = t0 + ext - b.safety if can_extend else None
                else:
                    self._deadline = self._extend_to = None
                t_iter = time.monotonic()
                best_move, best_real, _ = self._root(state, moves, d)
                done.append((d, best_move, best_real, time.monotonic() - t_iter))
                self._prev_iter_score = best_real
                self._unstable = self._is_unstable(done)
                moves = [best_move] + [m for m in moves if m != best_move]
                if abs(best_real) >= MATE_SCORE - MAX_PLY:
                    reason = "mate"
                    break
        except _Timeout as stop:
            while state.ply > start:  # desfaz os lances que a busca deixou no meio
                state.pop()
            partial = stop.args[0] if stop.args else None
            if partial is not None:  # a camada interrompida já achou algo
                best_move, best_real = partial
            reason = "tempo"
        finally:
            self._deadline = self._extend_to = None
        seconds = time.monotonic() - t0
        extended = seconds > cap
        if extended:
            self.extensions_used += 1
        self.last_score = best_real
        self.last_info = {
            "seconds": seconds,
            "depth": done[-1][0] if done else 0,
            "nodes": self.nodes - nodes0,
            "cap": cap,
            "extended": extended,
            "extensions_used": self.extensions_used,
            "stop": reason,
        }
        return best_move

    def _stable(self, done: list) -> bool:
        n = self.config.budget.stable_depths
        if len(done) < n:
            return False
        last = done[-n:]
        return len({m for _, m, _, _ in last}) == 1 and not self._unstable

    def _is_unstable(self, done: list) -> bool:
        b = self.config.budget
        if len(done) < 2 or done[-1][0] < b.unstable_from_depth:
            return False
        (_, m1, s1, _), (_, m0, s0, _) = done[-2], done[-1]
        return m0 != m1 or s0 <= s1 - b.drop_cp

    def _root(self, state: GameState, moves: list[Move], depth: int) -> tuple[Move, float, float]:
        """Busca na raiz até ``depth``; devolve (lance, escore real, escore com ruído).

        Com tempo esgotado levanta ``_Timeout`` com o melhor (lance, escore real)
        entre os lances já buscados por completo nesta camada, ou None."""
        noise = self.config.noise
        best_move, best_score, best_real = moves[0], -INF, -INF
        for i, move in enumerate(moves):
            # Um lance só pode superar o melhor (já com ruído) se o valor real passar de
            # best_score - noise. Abaixo desse piso o alfa-beta devolve só um limite
            # superior, e nem o maior ruído possível o faria vencer. O ruído entra
            # apenas na comparação, nunca em alpha, e não se aplica a mates.
            alpha = best_score - noise
            state.push(move)
            try:
                score = -self._negamax(state, depth - 1, -INF, -alpha, 1, self.check_extensions)
            except _Timeout:
                found = (best_move, best_real) if best_score > -INF else None
                raise _Timeout(found) from None
            state.pop()
            if self._extend_to is not None and depth >= self._unstable_depth():
                if i == 0:
                    prev = self._prev_iter_score
                    if prev is not None and score <= prev - self.config.budget.drop_cp:
                        self._unstable = True  # o lance da camada anterior piorou muito
                elif score > alpha and best_score > -INF:
                    self._unstable = True  # outro lance passou à frente
            if score <= alpha:
                continue
            real = score
            if noise and abs(score) < MATE_SCORE - MAX_PLY:
                score += self.rng.uniform(-noise, noise)
            if score > best_score:
                best_move, best_score, best_real = move, score, real
        return best_move, best_real, best_score

    def _unstable_depth(self) -> int:
        b = self.config.budget
        return b.unstable_from_depth if b is not None else MAX_PLY

    def _tick(self) -> None:
        self.nodes += 1
        if self._node_cap is not None and self.nodes > self._node_cap:
            raise _Timeout
        if (
            self._deadline is not None
            and self.nodes % _CLOCK_EVERY == 0
            and time.monotonic() > self._deadline
        ):
            if self._extend_to is not None and self._unstable:
                self._deadline, self._extend_to = self._extend_to, None  # usa a extensão
                return
            raise _Timeout

    def _negamax(
        self, state: GameState, depth: int, alpha: float, beta: float, ply: int, extensions: int
    ) -> float:
        self._tick()
        if state.is_repetition():
            return self._draw_score(ply)
        moves = state.legal_moves()
        if not moves:
            return -(MATE_SCORE - ply) if state.is_check() else self._draw_score(ply)
        # Extensão em xeque: o lado em xeque tem poucas respostas, então olhar um
        # meio-lance a mais custa pouco e evita julgar a posição no meio de um ataque.
        # ``extensions`` limita quantas vezes isso acontece numa mesma linha.
        if extensions and state.is_check():
            depth += 1
            extensions -= 1
        if depth <= 0:
            return self._quiescence(state, alpha, beta, ply, self.quiescence_depth)
        if not self.config.heuristics:
            for move in self._ordered(state, moves):
                state.push(move)
                score = -self._negamax(state, depth - 1, -beta, -alpha, ply + 1, extensions)
                state.pop()
                if score >= beta:
                    return score
                if score > alpha:
                    alpha = score
            return alpha

        key = state.key()
        entry = self._tt.get(key)
        tt_move = None
        if entry is not None:
            e_depth, e_score, e_flag, tt_move = entry
            if e_depth >= depth:
                score = _from_tt(e_score, ply)
                if (
                    e_flag == _EXACT
                    or (e_flag == _LOWER and score >= beta)
                    or (e_flag == _UPPER and score <= alpha)
                ):
                    return score
        alpha0, best_move = alpha, None
        for move in self._ordered_heuristic(state, moves, ply, tt_move):
            quiet = not (state.is_capture(move) or state.is_promotion(move))
            state.push(move)
            score = -self._negamax(state, depth - 1, -beta, -alpha, ply + 1, extensions)
            state.pop()
            if score >= beta:
                if quiet:
                    killers = self._killers.setdefault(ply, [])
                    if move not in killers:
                        killers.insert(0, move)
                        del killers[2:]
                    hkey = (state.white_to_move, move)
                    self._history[hkey] = self._history.get(hkey, 0) + depth * depth
                self._store(key, depth, score, _LOWER, move, ply)
                return score
            if score > alpha:
                alpha, best_move = score, move
        self._store(key, depth, alpha, _EXACT if alpha > alpha0 else _UPPER, best_move, ply)
        return alpha

    def _store(self, key, depth: int, score: float, flag: int, move, ply: int) -> None:
        if len(self._tt) >= _TT_MAX:
            self._tt.clear()
        old = self._tt.get(key)
        if old is not None and old[0] > depth:
            return  # mantém a entrada mais funda
        if move is None and old is not None:
            move = old[3]
        self._tt[key] = (depth, _to_tt(score, ply), flag, move)

    def _ordered_heuristic(self, state: GameState, moves: list[Move], ply: int, tt_move) -> list:
        """Lance da tabela primeiro, depois capturas e promoções (MVV-LVA), killers e
        os lances quietos pela history."""
        killers = self._killers.get(ply, ())
        history = self._history
        white = state.white_to_move

        def key(move: Move) -> float:
            if move == tt_move:
                return -1e12
            victim = state.captured_piece(move)
            promotion = state.is_promotion(move)
            if victim or promotion:
                score = 1e9 + 90 * promotion
                if victim:
                    attacker = _ORDER_VALUE[state.moving_piece(move)]
                    score += 10 * _ORDER_VALUE[victim] - attacker + 100
                return -score
            if move in killers:
                return -1e8 + killers.index(move)
            return -history.get((white, move), 0)

        return sorted(moves, key=key)

    def _draw_score(self, ply: int) -> float:
        """Empate visto do lado a jogar no nó: ruim para a raiz, bom para o adversário."""
        return -self.contempt if ply % 2 == 0 else self.contempt

    def _quiescence(
        self, state: GameState, alpha: float, beta: float, ply: int, qdepth: int
    ) -> float:
        stand_pat = evaluate(state, self.genome)
        if qdepth <= 0 or stand_pat >= beta:
            return stand_pat
        if stand_pat > alpha:
            alpha = stand_pat
        captures = [m for m in state.legal_moves() if state.is_capture(m) or state.is_promotion(m)]
        for move in self._ordered(state, captures):
            self._tick()
            state.push(move)
            score = -self._quiescence(state, -beta, -alpha, ply + 1, qdepth - 1)
            state.pop()
            if score >= beta:
                return score
            if score > alpha:
                alpha = score
        return alpha

    @staticmethod
    def _ordered(state: GameState, moves: list[Move]) -> list[Move]:
        """Capturas primeiro, por MVV-LVA (vítima mais valiosa, agressor menos valioso)."""

        def key(move: Move) -> int:
            victim = state.captured_piece(move)
            score = 0
            if victim:
                score = 10 * _ORDER_VALUE[victim] - _ORDER_VALUE[state.moving_piece(move)] + 100
            if state.is_promotion(move):
                score += 90
            return -score

        return sorted(moves, key=key)


def _to_tt(score: float, ply: int) -> float:
    """Mate guardado como distância a partir do nó, não da raiz."""
    if score >= MATE_SCORE - MAX_PLY:
        return score + ply
    if score <= -(MATE_SCORE - MAX_PLY):
        return score - ply
    return score


def _from_tt(score: float, ply: int) -> float:
    if score >= MATE_SCORE - MAX_PLY:
        return score - ply
    if score <= -(MATE_SCORE - MAX_PLY):
        return score + ply
    return score
