# Relatório de status do projeto

**Última atualização:** 2026-10-07
**Atualizado por:** agente de documentação ([.claude/agents/documentador.md](../.claude/agents/documentador.md))

Este relatório é atualizado depois de cada alteração concluída (PR mergeado) no repositório. Ele mostra o que já foi feito, o que está em andamento e o backlog de cada etapa.

Legenda: `[x]` concluído · `[~]` em andamento · `[ ]` não iniciado

---

## Resumo

| # | Etapa | Status | Progresso |
|---|-------|--------|-----------|
| 0 | Base do projeto (repositório, documentação, frentes de trabalho) | Em andamento | Repositório e documentação no `main` |
| 1 | Jogo de xadrez com regras validadas | Em andamento | Motor completo em revisão no [PR #2](https://github.com/lucas-kiozy/evolutiveChess/pull/2); falta o merge |
| 2 | Luna: IA evolutiva com algoritmo genético | Em andamento | Primeira versão em revisão no [PR #1](https://github.com/lucas-kiozy/evolutiveChess/pull/1) (rascunho) |
| 3 | Self-play paralelo e seleção de descendentes | Em andamento | Laço evolutivo paralelo no [PR #1](https://github.com/lucas-kiozy/evolutiveChess/pull/1); falta definir a aptidão sem mate |
| 4 | Medição de rating (meta ~1600) | Em andamento | Estimador de rating em revisão no [PR #4](https://github.com/lucas-kiozy/evolutiveChess/pull/4) |
| 5 | Luna jogando no Lichess | Em andamento | Bot do Lichess em revisão no [PR #4](https://github.com/lucas-kiozy/evolutiveChess/pull/4); falta conta BOT e ligar a Luna |

---

## O que já foi feito

| Data | Alteração | Etapa | Referência |
|------|-----------|-------|------------|
| 2026-10-07 | Repositório criado (vazio) | 0 | — |
| 2026-10-07 | README, relatório de status, referências e agente de documentação | 0 | Primeiro commit do `main` |

---

## Backlog por etapa

### Etapa 0 — Base do projeto

- [x] Criar o repositório `lucas-kiozy/evolutiveChess`
- [x] Documentação inicial: README, relatório de status, referências
- [x] Agente de documentação que atualiza este relatório a cada alteração concluída
- [ ] Definir as frentes (subagentes) de trabalho, no mínimo 3: motor de xadrez, Luna, rating e Lichess
- [ ] Estrutura de pacote Python (`pyproject.toml`, versão mínima do Python, layout `src/`)
- [ ] Ferramentas de qualidade: testes (`pytest`), lint e formatação
- [ ] Integração contínua (GitHub Actions) rodando os testes a cada PR

### Etapa 1 — Jogo de xadrez com regras validadas

**Critério de pronto:** um humano consegue jogar uma partida completa, e todas as regras passam em testes automatizados, incluindo contagem de nós por *perft* em posições de referência.

Em revisão no [PR #2](https://github.com/lucas-kiozy/evolutiveChess/pull/2) (pacote `chess_engine/`, Python puro; interface descrita em `chess_engine/API.md`). Os itens marcados `[~]` estão no PR e passam a `[x]` quando ele for mergeado.

- [~] Representação do tabuleiro e das peças
- [~] Geração de lances de todas as peças
- [~] Roque (curto e longo, com todas as restrições)
- [~] Captura *en passant*
- [~] Promoção de peão
- [~] Filtro de lances legais (não deixar o próprio rei em xeque)
- [~] Detecção de xeque, xeque-mate e afogamento
- [~] Empates: repetição tripla e quíntupla, regras dos 50 e 75 lances, material insuficiente
- [~] `play_game` com contagem de lances e de xeques por cor, usada na aptidão da Luna
- [~] Testes de *perft* em 21 posições de referência
- [~] 300 partidas aleatórias comparadas com `python-chess`, sem divergência
- [~] Jogo no terminal: `python -m chess_engine`
- [ ] Integração contínua (GitHub Actions) rodando os testes a cada PR

### Etapa 2 — Luna: IA evolutiva com algoritmo genético

**Critério de pronto:** uma Luna joga partidas completas usando parâmetros vindos de um genoma, e uma população de Lunas pode ser criada, cruzada e mutada.

Em andamento no [PR #1](https://github.com/lucas-kiozy/evolutiveChess/pull/1) (rascunho, pacote `luna/`, 15 testes). Os itens marcados `[~]` estão no PR e passam a `[x]` quando ele for mergeado.

- [~] Definir o genoma: 14 pesos de avaliação (`luna/genome.py`)
- [~] Função de avaliação parametrizada pelo genoma (`luna/evaluation.py`)
- [~] Busca de lances: alfa-beta com busca de quiescência (`luna/search.py`)
- [~] Inicialização da população
- [~] Operadores genéticos: seleção por torneio, cruzamento uniforme, mutação gaussiana (`luna/evolution.py`)
- [~] Elitismo (preservar os melhores entre gerações)
- [~] Salvar e carregar gerações com retomada do treino (`luna/storage.py`, pasta `luna/runs/<nome>/`)
- [~] Linha de comando: `python -m luna train` e `python -m luna show`
- [ ] Histórico de evolução por geração (aptidão média e máxima)
- [ ] Trocar o adaptador provisório (`python-chess`) pelo motor próprio da etapa 1, via `luna/game_interface.py`
- [ ] Melhorar a velocidade: hoje cerca de 50 s por partida por núcleo

### Etapa 3 — Self-play paralelo e seleção de descendentes

**Critério de pronto:** uma geração inteira joga em paralelo, a aptidão é calculada pelo critério definido e a próxima geração é gerada automaticamente, em ciclo.

- [~] Partidas Luna contra Luna em paralelo (`ProcessPoolExecutor`, `luna/match.py`) — PR #1
- [ ] Alternância de cores garantida (cada par joga de brancas e de pretas)
- [ ] Limite de lances por partida, para evitar partidas infinitas
- [~] Cálculo de aptidão (`luna/fitness.py`) — PR #1:
  - [~] 1º critério: vitória com **menos lances** até o xeque-mate
  - [~] 2º critério (desempate): **menos xeques** dados durante a partida
  - [ ] Ranquear Lunas que não dão mate (ver "Decisões em aberto", item 1)
- [~] Laço contínuo: jogar → avaliar → selecionar → reproduzir → repetir — PR #1
- [ ] Treino longo (muitas gerações) e análise dos resultados
- [ ] Registro das partidas (PGN) e métricas de cada geração

### Etapa 4 — Medição de rating (meta ~1600)

**Critério de pronto:** o rating estimado da melhor Luna é calculado de forma reprodutível, com intervalo de confiança, contra adversários de força conhecida.

Em revisão no [PR #4](https://github.com/lucas-kiozy/evolutiveChess/pull/4) (pacote `rating/`, guia em `rating/GUIA.md`). Os itens `[~]` passam a `[x]` quando ele for mergeado.

- [~] Adversário de referência: Stockfish com `UCI_Elo` calibrado (piso de 1320, o mínimo do Stockfish)
- [~] Séries de partidas em paralelo contra esse adversário
- [~] Estimativa do rating por máxima verossimilhança no modelo de Elo, com intervalo de confiança de 90%
- [~] Critério "pronta para o Lichess": limite inferior do IC 90% maior ou igual a 1600
- [~] Interface comum de jogador: `choose_move(fen, lances_uci) -> uci`
- [ ] Ligar a Luna real ao estimador (adaptador curto, exemplo em `rating/GUIA.md`)
- [ ] Medir a melhor Luna de cada geração

### Etapa 5 — Luna jogando no Lichess

**Critério de pronto:** a Luna joga partidas no Lichess por uma conta BOT, uma partida por vez, e continua evoluindo com os resultados.

Em revisão no [PR #4](https://github.com/lucas-kiozy/evolutiveChess/pull/4) (pacote `lichess_bot/`, guia em `lichess_bot/GUIA.md`).

- [~] Integração com a Bot API oficial do Lichess
- [~] Uma partida por vez, em sequência
- [~] Cada partida gravada em `lichess_bot/runs/`, com gancho `on_game_finished` para o aprendizado
- [ ] **Lucas:** criar a conta BOT e o token de API quando a Luna chegar a ~1600 (o token fica fora do repositório)
- [ ] Ligar a Luna real ao bot
- [ ] Definir como a Luna aprende com as partidas do Lichess (ver "Decisões em aberto", item 5)
- [ ] Acompanhar o rating da Luna no Lichess ao longo do tempo

---

## Decisões em aberto

Pontos que precisam de decisão do Lucas ou da frente responsável antes ou durante a implementação:

1. **Como ranquear Lunas que não dão mate.** O critério atual cobra vitórias (menos lances até o mate) com desempate por menos xeques. Ainda não está definido quanto vale um empate (afogamento, repetição, 50 lances, material insuficiente) nem uma partida interrompida pelo limite de lances. Isso já é bloqueante: na primeira medição do PR #1, com busca de profundidade 2, houve **0 mates em 8 partidas**, então sem essa regra a seleção não distingue as Lunas.
2. **Pontuação de derrotas.** Se uma Luna perde, ela recebe aptidão zero ou ganha algo por ter resistido mais lances?
3. **Motor de regras próprio ou biblioteca.** Implementar as regras do zero ou usar uma biblioteca consolidada como [`python-chess`](https://python-chess.readthedocs.io/) como referência de validação. Por enquanto a Luna usa `python-chess` como adaptador provisório, isolado em `luna/game_interface.py`, para trocar pelo motor próprio quando ele ficar pronto.
4. **Como medir "rating equivalente a 1600".** Proposta no PR #4: partidas contra Stockfish com Elo limitado e liberação quando o limite inferior do intervalo de confiança de 90% chegar a 1600. Vira decisão quando o PR for mergeado.
5. **Como a Luna aprende com as partidas do Lichess.** No self-play há uma população inteira; no Lichess joga uma Luna por vez. Falta definir como os resultados online alimentam a evolução.

---

## Histórico de atualizações deste relatório

| Data | O que mudou |
|------|-------------|
| 2026-10-07 | Criação do relatório com as etapas definidas pelo Lucas e o backlog inicial |
| 2026-10-07 | Etapas 2 e 3 em andamento com o PR #1 (Luna); decisão sobre partidas sem mate passa a ser bloqueante |
| 2026-10-07 | Etapa 1 em revisão com o PR #2 (motor de xadrez com todas as regras) |
| 2026-10-07 | Etapas 4 e 5 em revisão com o PR #4 (estimador de rating e bot do Lichess) |
