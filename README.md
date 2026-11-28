# evolutiveChess

Um jogo de xadrez em Python com uma inteligência evolutiva chamada **Luna**. A Luna aprende jogando contra outras Lunas, em várias partidas em paralelo, e cada geração seleciona os melhores descendentes por algoritmo genético. Quando a Luna atingir rating equivalente a ~1600, ela passa a jogar no [Lichess](https://lichess.org/), uma partida por vez, e continua se aperfeiçoando.

> **Status atual:** as etapas 1 a 3 estão no `main`: o motor de xadrez com todas as regras e a Luna evoluindo por self-play paralelo. A medição de rating e o bot do Lichess também já estão no `main`; a Luna já passou de 1600. A Luna oficial hoje é a `luna-v5`, promovida em 2026-11-20 depois de vencer a `luna-v4` por +25 ± 10 Elo; ela mede 2090 ± 43 (Stockfish e Leela Chess Zero) e está indicada em `luna/versions/oficial.txt`. Uma candidata só substitui a oficial se vencer o match de promoção.
> Desde 2026-11-28, nas partidas oficiais a Luna administra o próprio tempo: até 20 s na grande maioria dos lances e no máximo 5 lances por partida acima disso (veja "Como a Luna pensa").
> O relatório completo do que já foi feito e do que falta está em [docs/STATUS.md](docs/STATUS.md).

## Etapas do projeto

| # | Etapa | Status |
|---|-------|--------|
| 1 | Jogo de xadrez funcional com todas as regras validadas | **Concluída** ([PR #2](https://github.com/lucas-kiozy/evolutiveChess/pull/2)) |
| 2 | Luna: IA evolutiva com algoritmo genético | **Concluída** ([PR #1](https://github.com/lucas-kiozy/evolutiveChess/pull/1)) |
| 3 | Self-play paralelo: Luna contra Luna, seleção dos melhores descendentes | **Concluída** ([PR #1](https://github.com/lucas-kiozy/evolutiveChess/pull/1)); treino longo em andamento |
| 4 | Medição de rating (meta: ~1600) | **Meta atingida:** a Luna oficial (`luna-v5`) mede 2090 ± 43, juntando partidas contra o Stockfish e a Leela Chess Zero |
| 5 | Luna jogando no Lichess, partida a partida, e evoluindo | Em andamento: bot pronto e ligado à Luna oficial; falta a conta BOT do Lucas |

O detalhamento de cada etapa, com backlog e critérios de pronto, está em [docs/STATUS.md](docs/STATUS.md).

## Critério de aptidão da Luna

Definido pelo Lucas para escolher os melhores descendentes. Cada partida dá pontos à Luna, e os pontos são somados em todas as partidas da geração:

| Resultado | Pontos |
|-----------|--------|
| Vitória (xeque-mate) | +5 |
| Vitória por desistência do adversário | +5 desde a revisão do AG de 2026-11-28 (os treinos até o `treino-v4` davam +6, com 1 de bônus) |
| Empate | +2 |
| Derrota | -1 |

Se duas Lunas empatarem na soma, os desempates são, nesta ordem:

1. **Mais pontos de captura** em empates e derrotas: peão 0,1, cavalo 0,3, bispo 0,4, torre 0,6, dama 2.
2. **Menos xeques nas vitórias:** o ideal é vencer sendo objetivo no ataque.
3. **Menos lances até o xeque-mate.**

## Como a Luna pensa

A Luna é escrita em Python puro, motor de regras inclusive, e analisa cerca de **19 mil posições (nós) por segundo** (medido em 2026-11-27 em posições reais, 4 partidas em paralelo). Para cada lance ela faz uma busca alfa-beta com aprofundamento iterativo: olha 1 meio-lance à frente, depois 2, 3 e assim por diante, reaproveitando o que aprendeu na camada anterior. Ajudam a busca a tabela de transposição, os lances killer, a heurística history, a quiescência sobre capturas e as extensões em xeque. A avaliação de cada posição vem dos 21 genes do genoma, que o algoritmo genético ajusta.

| Onde | Profundidade mínima (meios-lances) | Tempo por lance |
|------|-------------------------------------|-----------------|
| Partidas oficiais (rating, promoção, Lichess) | 2 nos lances 1 a 9, 4 nos 10 a 16, 5 do 17 em diante, e até 4 a mais quando sobra tempo | Orçamento: teto normal de 20 s; para cedo se o melhor lance se repete por 3 camadas; passa de 20 s (até 40 s) só se o melhor lance mudar ou a avaliação cair meio peão, e no máximo em 5 lances por partida |
| Treino (Luna contra Luna) | 2/3/4/5 nos lances 1 a 10, 11 a 29, 30 a 45 e 46 em diante | Limite de 200 mil nós por lance desde o `treino-v5` (de ~10 a ~20 s, igual em qualquer máquina); os treinos até o `treino-v4` usavam 14 s fixos |

No Lichess a Luna abre sempre 1.e4 de brancas e 1...c6 de pretas, sorteia entre lances que diferem até 5 centipeões para não repetir partidas e encolhe os tetos de tempo conforme o relógio. O desafio automático é 15+5. Nas medições de rating não há sorteio, e as partidas começam do livro de aberturas, com pares de cores trocadas.

Na validação do orçamento de tempo (128 partidas, 2026-11-28), nenhuma das 96 partidas da Luna passou de 5 lances acima de 20 s. A mediana ficou em 6,2 s por lance, e 93% dos lances levaram até 20 s. Contra a Leela de 16 nós, a Luna com orçamento fez 14 pontos em 32, contra 9,5 da versão de 14 s fixos nas mesmas aberturas. Os detalhes estão em [docs/STATUS.md](docs/STATUS.md).

## Organização do trabalho

O projeto é tocado por frentes de trabalho com focos diferentes, cada uma numa conversa própria do projeto no Claude:

| Frente | Responsabilidade |
|--------|------------------|
| Motor de xadrez | Tabuleiro, geração de lances legais, validação de todas as regras, testes |
| Luna | Genoma, função de avaliação, busca, operadores genéticos, self-play paralelo |
| Rating e Lichess | Medição de rating contra adversários calibrados, integração com a API de bots do Lichess |
| Documentação | Este README e o relatório em `docs/`, atualizados a cada alteração concluída |

Por enquanto só a frente de documentação tem um agente definido no repositório, em [.claude/agents/documentador.md](.claude/agents/documentador.md).

O repositório também traz três skills do Claude, em `.claude/skills/`, que usam o código do projeto:

| Skill | Para que serve |
|-------|----------------|
| `luna-treino` | Treinar a Luna: rodar ou retomar gerações e resumir o treino |
| `validar-regras-xadrez` | Conferir se um lance ou uma posição é legal no `chess_engine` e explicar o motivo |
| `relatorio-evolucao-luna` | Relatório de evolução da Luna: tendência de mates, genes que mudaram, gráfico e Elo entre gerações |

## Estrutura do repositório

```
.
├── README.md                   # visão geral (este arquivo)
├── chess_engine/               # motor de xadrez em Python puro (etapa 1)
│   ├── API.md                  # interface pública do motor
│   └── tests/                  # regras, perft e comparação com python-chess
├── luna/                       # IA evolutiva: genoma, busca, algoritmo genético (etapas 2 e 3)
│   └── versions/               # versões nomeadas da Luna
├── rating/                     # estimativa de rating contra o Stockfish (etapa 4; guia em GUIA.md)
├── lichess_bot/                # bot do Lichess, uma partida por vez (etapa 5; guia em GUIA.md)
├── docs/
│   ├── STATUS.md               # relatório: o que foi feito e backlog
│   └── REFERENCIAS.md          # base científica e técnica do projeto
├── tools/                      # utilitários, como o comparador de velocidade dos backends
├── plans/                      # planos de implementação
├── pyproject.toml              # pacote e dependências (pip install -e ".[dev]")
├── .github/workflows/ci.yml    # testes e lint a cada PR
└── .claude/
    ├── agents/documentador.md  # agente que mantém a documentação
    └── skills/                 # skills de treino, validação de regras e relatório da Luna
```

## Como executar

Requer Python 3.10 ou mais novo. O motor não tem dependências. A Luna usa o motor próprio por padrão; `python-chess` só é necessário no backend alternativo e nos testes de comparação.

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

# treinar a Luna: 10 gerações de 8 Lunas, 18 partidas por Luna e 2 campeãs passadas
python -m luna train --run-dir treinos/meu-treino --generations 10 --population 8 --games-per-luna 18 --hall-of-fame 2

# ver o histórico e a melhor Luna do treino
python -m luna show --run-dir treinos/meu-treino

# salvar a melhor Luna como versão nomeada (vai para luna/versions/) e listar as versões
python -m luna export --run-dir treinos/meu-treino --name luna-v1
python -m luna versions

# match de promoção: a candidata só vira a Luna oficial se vencer a atual (docs/CATRACA.md)
python -m luna promote --run-dir treinos/meu-treino --name luna-v6 --out desafios/luna-v6

# várias candidatas: pré-seleção de 32 partidas e desafio da melhor, retomável
tools/catraca.sh desafios/v6 candidata-a.json candidata-b.json

# ajustar os pesos da avaliação pelo método de Texel (gera uma candidata para a catraca)
python -m luna.texel --partidas treinos/meu-treino --base luna-v5 --saida candidata-texel.json

# efeito controlado de um gene, com clones, no treino e nas condições oficiais
python tools/confronto_genes.py --base luna-v5 --gene check_extension --valores 1 2 3 \
    --condicoes treino oficial --pares 343 --out confrontos/check-extension

# testes de todos os pacotes
python -m pytest
```

Rodar `python -m luna train` de novo com o mesmo `--run-dir` continua o treino de onde parou. Desde a revisão do AG de 2026-11-28, um treino novo é **congelado**: a configuração salva é lida como está, cada geração grava a configuração e o SHA do código, e mudar busca, limite ou avaliação exige um treino novo. Os treinos antigos continuam rodando como antes.

Para medir o rating da Luna oficial contra o Stockfish e para colocá-la no Lichess, use `--player luna.player:official_factory` (rating) ou `--player luna.player:lichess_factory` (Lichess, com 1.e4 / 1...c6 fixos e um ruído pequeno para não repetir partidas) e siga [rating/GUIA.md](rating/GUIA.md) e [lichess_bot/GUIA.md](lichess_bot/GUIA.md).

## Referências

A base científica das escolhas do projeto (algoritmos genéticos aplicados a xadrez, sistemas de rating) está em [docs/REFERENCIAS.md](docs/REFERENCIAS.md).
