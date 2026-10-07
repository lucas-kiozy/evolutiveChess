# chess_engine: interface pública

Motor de xadrez em Python puro (sem dependências), com todas as regras:
roque (incluindo as restrições de xeque e casas atacadas), en passant
(incluindo a cravada horizontal), promoção para qualquer peça, xeque-mate,
afogamento, material insuficiente, regras dos 50 e 75 lances e repetição
tripla/quíntupla.

Este arquivo é o contrato com quem usa o motor (a Luna e a integração com o
Lichess). Mudanças incompatíveis nele devem ser combinadas antes.

## Convenções

| Conceito | Representação |
|---|---|
| Cor | `WHITE = 1`, `BLACK = -1` |
| Casa | inteiro 0..63, `a1 = 0`, `h1 = 7`, `a8 = 56`, `h8 = 63` (`square_index("e4") == 28`, `SQUARE_NAMES[28] == "e4"`) |
| Peça | `PAWN=1, KNIGHT=2, BISHOP=3, ROOK=4, QUEEN=5, KING=6`; positivo = branca, negativo = preta, `0` = vazio |
| Lance | inteiro `origem \| destino << 6 \| promocao << 12` |

Lances são inteiros para a geração ser rápida. Use as funções abaixo em vez de
mexer nos bits:

```python
from chess_engine import make_move, move_from, move_to, move_promotion, move_to_uci

move_to_uci(m)        # "e2e4", "e7e8q"
move_from(m), move_to(m), move_promotion(m)   # promoção = QUEEN/ROOK/BISHOP/KNIGHT ou 0
make_move(12, 28)     # e2e4
```

## Board

```python
from chess_engine import Board, WHITE, BLACK

board = Board()                 # posição inicial
board = Board(fen)              # qualquer FEN; ValueError se inválida
board.fen()
board.copy()                    # cópia independente, com histórico
```

### Lances

| Método | O que faz |
|---|---|
| `legal_moves()` | lista de lances legais (cópia nova a cada chamada, pode alterar) |
| `push(move)` | aplica um lance legal (não valida, por velocidade) |
| `pop()` | desfaz o último lance e o devolve |
| `parse_uci(s)` / `push_uci(s)` | converte/aplica `"e2e4"`; `ValueError` se ilegal |
| `parse_san(s)` / `push_san(s)` | o mesmo para SAN (`"Nf3"`, `"O-O"`, `"e8=Q+"`) |
| `san(move)` | SAN do lance na posição atual |
| `is_capture(move)`, `is_castling(move)`, `gives_check(move)` | classificam um lance legal |
| `peek()`, `move_stack`, `ply` | último lance, lista de lances, número de meios-lances |

`push`/`pop` são a forma barata de explorar a árvore numa busca
(minimax/alfa-beta): faça `push`, avalie, `pop`.

### Estado e regras

| Membro | O que é |
|---|---|
| `turn` | cor de quem joga |
| `squares` | lista de 64 peças (só leitura, por favor) |
| `piece_at(sq)`, `king_square(color)` | consultas diretas |
| `is_attacked(sq, by_color)` | a casa é atacada por aquela cor? |
| `castling`, `ep_square`, `halfmove_clock`, `fullmove_number` | campos da FEN |
| `key()` | hash Zobrist de 64 bits (bom para tabela de transposição) |
| `is_check()`, `is_checkmate()`, `is_stalemate()` | |
| `is_insufficient_material()` | K×K, K+menor×K, bispos todos da mesma cor |
| `is_fifty_moves()`, `is_seventyfive_moves()` | |
| `is_threefold_repetition()`, `is_fivefold_repetition()` | |
| `outcome(claim_draw=True)` | `Outcome` ou `None` se a partida continua |
| `is_game_over(claim_draw=True)` | |

`outcome()` devolve `Outcome(winner, termination)`:
`winner` é `WHITE`, `BLACK` ou `None`; `termination` é um de `checkmate`,
`stalemate`, `insufficient_material`, `seventyfive_moves`,
`fivefold_repetition`, `fifty_moves`, `threefold_repetition`.
`outcome.result()` dá `"1-0"`, `"0-1"` ou `"1/2-1/2"`.

Com `claim_draw=True` (padrão) os empates que na FIDE dependem de reivindicação
(50 lances, tripla repetição) encerram a partida, o que evita partidas
infinitas entre IAs. Com `claim_draw=False` valem só os automáticos.

### Contadores para a aptidão da Luna

| Método | O que conta |
|---|---|
| `moves_made(color)` | lances feitos por aquela cor nesta partida |
| `checks_given(color)` | xeques dados por aquela cor (o lance de mate conta como xeque) |

Ambos acompanham `push`/`pop`, então continuam certos depois de uma busca.

## Partida completa

```python
import random
from chess_engine import play_game

def aleatorio(board):
    return random.choice(board.legal_moves())

result = play_game(aleatorio, aleatorio, max_plies=400)
result.outcome            # Outcome; termination "max_plies" se bateu o limite
result.winner             # WHITE, BLACK ou None
result.moves              # lances em UCI
result.moves_by(WHITE)    # lances do vencedor = critério 1 da Luna
result.checks_by(WHITE)   # xeques dados     = critério de desempate
result.final_fen
```

Um jogador é qualquer função `jogador(board) -> lance`. Ele recebe o tabuleiro
da própria partida e pode usar `push`/`pop` para pensar, desde que devolva a
posição como recebeu. `play_game` levanta `ValueError` se o lance for ilegal.

`Board` e `play_game` não têm estado global, então rodam sem problema em
processos paralelos (`multiprocessing`/`concurrent.futures.ProcessPoolExecutor`).

## Desempenho

Python puro, medido neste ambiente: cerca de 1 milhão de nós de perft por
segundo nas folhas, e cerca de 27 mil lances por segundo em partidas aleatórias
completas (gerando lances e checando fim de jogo a cada lance).

## Jogar no terminal

```
python -m chess_engine                 # dois jogadores
python -m chess_engine --aleatorio     # contra lances aleatórios
python -m chess_engine --aleatorio --pretas
```

## Testes

```
python -m pytest chess_engine/tests            # rápido (~2 s)
CHESS_SLOW=1 python -m pytest chess_engine/tests   # inclui perft profundo
```

* `test_perft.py`: 21 posições de referência (chessprogramming.org e o conjunto
  de casos táticos de Martin Sedlak), cobrindo roque, en passant, promoção,
  cravadas e afogamento.
* `test_rules.py`: cada regra testada isoladamente, mais a API.
* `test_against_python_chess.py`: partidas aleatórias comparadas lance a lance
  com a biblioteca python-chess (lances legais, xeque, FEN, SAN e resultado).
  Só roda se `chess` estiver instalado (`pip install chess`).
