# evolutiveChess

Um jogo de xadrez em Python com uma inteligência evolutiva chamada **Luna**. A Luna aprende jogando contra outras Lunas, em várias partidas em paralelo, e cada geração seleciona os melhores descendentes por algoritmo genético. Quando a Luna atingir rating equivalente a ~1600, ela passa a jogar no [Lichess](https://lichess.org/), uma partida por vez, e continua se aperfeiçoando.

> **Status atual:** as etapas 1 a 3 estão no `main`: o motor de xadrez com todas as regras e a Luna evoluindo por self-play paralelo. A medição de rating e o bot do Lichess também já estão no `main`; falta a Luna chegar a ~1600.
> O relatório completo do que já foi feito e do que falta está em [docs/STATUS.md](docs/STATUS.md).

## Etapas do projeto

| # | Etapa | Status |
|---|-------|--------|
| 1 | Jogo de xadrez funcional com todas as regras validadas | **Concluída** ([PR #2](https://github.com/lucas-kiozy/evolutiveChess/pull/2)) |
| 2 | Luna: IA evolutiva com algoritmo genético | **Concluída** ([PR #1](https://github.com/lucas-kiozy/evolutiveChess/pull/1)) |
| 3 | Self-play paralelo: Luna contra Luna, seleção dos melhores descendentes | **Concluída** ([PR #1](https://github.com/lucas-kiozy/evolutiveChess/pull/1)); treino longo em andamento |
| 4 | Medição de rating (meta: ~1600) | Em andamento: estimador pronto, falta medir a Luna |
| 5 | Luna jogando no Lichess, partida a partida, e evoluindo | Em andamento: bot pronto, aguarda a Luna chegar a ~1600 |

O detalhamento de cada etapa, com backlog e critérios de pronto, está em [docs/STATUS.md](docs/STATUS.md).

## Critério de aptidão da Luna

Definido pelo Lucas para escolher os melhores descendentes. Cada partida dá pontos à Luna, e os pontos são somados em todas as partidas da geração:

| Resultado | Pontos |
|-----------|--------|
| Vitória (xeque-mate) | +5 |
| Empate | +2 |
| Derrota | -1 |

Se duas Lunas empatarem na soma, os desempates são, nesta ordem:

1. **Mais pontos de captura** em empates e derrotas: peão 0,1, cavalo 0,3, bispo 0,4, torre 0,6, dama 2.
2. **Menos xeques nas vitórias:** o ideal é vencer sendo objetivo no ataque.
3. **Menos lances até o xeque-mate.**

## Organização do trabalho

O projeto é tocado por frentes de trabalho com focos diferentes, cada uma numa conversa própria do projeto no Claude:

| Frente | Responsabilidade |
|--------|------------------|
| Motor de xadrez | Tabuleiro, geração de lances legais, validação de todas as regras, testes |
| Luna | Genoma, função de avaliação, busca, operadores genéticos, self-play paralelo |
| Rating e Lichess | Medição de rating contra adversários calibrados, integração com a API de bots do Lichess |
| Documentação | Este README e o relatório em `docs/`, atualizados a cada alteração concluída |

Por enquanto só a frente de documentação tem um agente definido no repositório, em [.claude/agents/documentador.md](.claude/agents/documentador.md).

## Estrutura do repositório

```
.
├── README.md                 # visão geral (este arquivo)
├── chess_engine/             # motor de xadrez em Python puro (etapa 1)
├── luna/                     # IA evolutiva: genoma, busca, algoritmo genético (etapas 2 e 3)
│   └── versions/             # versões nomeadas da Luna
├── rating/                   # estimativa de rating contra o Stockfish (etapa 4; guia em GUIA.md)
├── lichess_bot/              # bot do Lichess, uma partida por vez (etapa 5; guia em GUIA.md)
├── plans/                    # planos de implementação
├── pyproject.toml            # pacote e dependências (pip install -e ".[dev]")
├── .github/workflows/ci.yml  # testes e lint a cada PR
│   ├── API.md                # interface pública do motor
│   └── tests/                # regras, perft e comparação com python-chess
├── docs/
│   ├── STATUS.md             # relatório: o que foi feito e backlog
│   └── REFERENCIAS.md        # base científica e técnica do projeto
└── .claude/agents/
    └── documentador.md       # agente que mantém a documentação
```

## Como executar

Requer Python 3.10 ou mais novo. O motor não tem dependências; a Luna usa `python-chess` só no backend `python-chess` (o padrão por enquanto).

```bash
# instalar com as dependências de desenvolvimento e de todos os pacotes
pip install -e ".[dev]"
```

```bash
# jogar no terminal (você contra você)
python -m chess_engine

# jogar contra lances aleatórios, de pretas
python -m chess_engine --aleatorio --pretas

# começar de uma posição FEN
python -m chess_engine --fen "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3"

# treinar a Luna: 10 gerações de 8 Lunas, usando o motor próprio
python -m luna train --run-dir treinos/meu-treino --generations 10 --population 8 --backend chess_engine

# ver o histórico e a melhor Luna do treino
python -m luna show --run-dir treinos/meu-treino

# salvar a melhor Luna como versão nomeada (vai para luna/versions/) e listar as versões
python -m luna export --run-dir treinos/meu-treino --name luna-v1
python -m luna versions

# testes de todos os pacotes
python -m pytest
```

Rodar `python -m luna train` de novo com o mesmo `--run-dir` continua o treino de onde parou.

Para medir o rating da Luna contra o Stockfish e para colocá-la no Lichess, siga [rating/GUIA.md](rating/GUIA.md) e [lichess_bot/GUIA.md](lichess_bot/GUIA.md).

## Referências

A base científica das escolhas do projeto (algoritmos genéticos aplicados a xadrez, sistemas de rating) está em [docs/REFERENCIAS.md](docs/REFERENCIAS.md).
