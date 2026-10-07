# Rating offline da Luna

Este pacote responde a uma pergunta: **a Luna já está perto de 1600?**
Ele joga a Luna contra o Stockfish com força limitada (`UCI_LimitStrength` +
`UCI_Elo`) e estima o rating por máxima verossimilhança no modelo de Elo.

## Requisitos

```bash
pip install -r rating/requirements.txt
sudo apt install stockfish        # ou defina STOCKFISH_PATH
```

## Uso

```bash
# Teste da instalação com um jogador aleatório (rápido, ~segundos)
python -m rating --player rating.player:random_player_factory --games 8 --movetime 0.01

# Medição de verdade (relógio do Stockfish em 60s+0,6s, como na calibração oficial)
python -m rating --player meu_modulo:fabrica_da_luna --games 60 --parallel 4
```

Saída típica:

```
Partidas: 60 | pontos: 31 (52%)
Rating estimado: 1612 ± 48 (IC 1.64σ: 1533 a 1691), escala CCRL/UCI_Elo
Alvo 1600: ainda não atingido.
```

Cada partida fica em `rating/runs/history.jsonl` (com PGN).

## Ligando a Luna

O estimador aceita qualquer objeto com
`choose_move(fen: str, legal_moves: list[str]) -> str` (lances em UCI).
Métodos opcionais: `new_game(color)` e `set_clock(ms_restantes, ms_incremento)`.
A fábrica precisa ser uma função de nível de módulo (sem argumentos), porque
cada partida roda num processo separado. Exemplo de adaptador:

```python
# luna_player.py (exemplo; os nomes da Luna podem mudar)
from luna.storage import RunStorage
from luna.search import Searcher, SearchConfig
from luna.adapters.python_chess import PythonChessGame

class LunaPlayer:
    def __init__(self, run_dir="luna/runs/padrao"):
        genome = RunStorage(run_dir).load_best()
        self.searcher = Searcher(genome, SearchConfig())

    def choose_move(self, fen, legal_moves):
        state = PythonChessGame(fen)
        return state.uci(self.searcher.choose_move(state))

def luna_factory():
    return LunaPlayer()
```

## Como a estimativa funciona

1. Começa contra o Stockfish 1320 (mínimo do Stockfish 16).
2. Joga lotes em paralelo alternando cores; depois de cada lote recalcula o
   rating e move o adversário para perto da estimativa, onde cada partida
   informa mais (a informação de Fisher por partida, `p(1-p)`, é máxima em 50%).
3. Para ao atingir `--games` ou o erro-padrão `--stderr` (padrão 40).
4. **Pronta para o Lichess** quando o limite inferior do intervalo de 90% já
   passa do alvo (`--target`, padrão 1600). Assim um lote de sorte não basta.

Quantas partidas? Perto de 50% de pontuação, o erro-padrão é cerca de
`347 / √N`: 40 partidas → ~55 pontos; 160 → ~27.

## Limitações (importante)

- **Escala:** o `UCI_Elo` do Stockfish é calibrado no ritmo 60s+0,6s e
  ancorado na lista CCRL 40/4 (documentação oficial do Stockfish). Não é a
  escala do Lichess (Glicko-2) nem a da FIDE. O número daqui serve para decidir
  quando ir ao Lichess; o rating real só aparece jogando lá.
- **Piso de 1320:** abaixo disso não há âncora calibrada; o relatório só diz
  "abaixo de ~1320".
- `--movetime` acelera os testes, mas foge do ritmo calibrado.
- O Stockfish recebe só a posição (FEN), sem o histórico; a repetição é
  arbitrada pelo python-chess, não pelo Stockfish.

## Referências

- Elo, A. E. (1978). *The Rating of Chessplayers, Past and Present*. Arco.
- Bradley, R. A.; Terry, M. E. (1952). Rank analysis of incomplete block
  designs: I. The method of paired comparisons. *Biometrika*, 39(3/4), 324–345.
- Glickman, M. E. (1999). Parameter estimation in large dynamic paired
  comparison experiments. *Journal of the Royal Statistical Society C*, 48(3),
  377–394.
- Coulom, R. (2008). Whole-History Rating: A Bayesian rating system for players
  of time-varying strength. *Computers and Games*, LNCS 5131, 113–124.
- Stockfish, opção `UCI_Elo` no README oficial:
  https://github.com/official-stockfish/Stockfish
