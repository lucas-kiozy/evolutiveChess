# Relatório de status do projeto

**Última atualização:** 2026-10-07
**Atualizado por:** agente de documentação ([.claude/agents/documentador.md](../.claude/agents/documentador.md))

Este relatório é atualizado depois de cada alteração concluída no repositório. Itens de PRs ainda em revisão aparecem como `[~]` e só passam a `[x]` quando o PR é mergeado no `main`.

**Último commit do `main` coberto:** `b96942f`

Legenda: `[x]` concluído no `main` · `[~]` em andamento ou em PR aberto · `[ ]` não iniciado

---

## Resumo

| # | Etapa | Status | Progresso |
|---|-------|--------|-----------|
| 0 | Base do projeto (repositório, documentação, frentes de trabalho) | Em andamento | Repositório e documentação no `main` |
| 1 | Jogo de xadrez com regras validadas | **Concluída** | Motor mergeado no `main` pelo [PR #2](https://github.com/lucas-kiozy/evolutiveChess/pull/2) |
| 2 | Luna: IA evolutiva com algoritmo genético | **Concluída** | Luna no `main` pelo [PR #1](https://github.com/lucas-kiozy/evolutiveChess/pull/1); faltam ajustes (backend padrão, versão `luna-v1`) |
| 3 | Self-play paralelo e seleção de descendentes | **Concluída** | Laço evolutivo paralelo com a régua 5/2/-1 no `main` pelo [PR #1](https://github.com/lucas-kiozy/evolutiveChess/pull/1); treino longo em andamento |
| 4 | Medição de rating (meta ~1600) | Em andamento | Estimador de rating em revisão no [PR #4](https://github.com/lucas-kiozy/evolutiveChess/pull/4) |
| 5 | Luna jogando no Lichess | Em andamento | Bot do Lichess em revisão no [PR #4](https://github.com/lucas-kiozy/evolutiveChess/pull/4); falta conta BOT e ligar a Luna |

---

## O que já foi feito

| Data | Alteração | Etapa | Referência |
|------|-----------|-------|------------|
| 2026-10-07 | Repositório criado (vazio) | 0 | — |
| 2026-10-07 | README, relatório de status, referências e agente de documentação | 0 | Primeiro commit do `main` |
| 2026-10-07 | Motor de xadrez com todas as regras, FEN, SAN, PGN e jogo no terminal | 1 | [PR #2](https://github.com/lucas-kiozy/evolutiveChess/pull/2) |
| 2026-10-07 | Luna: genoma, avaliação, busca alfa-beta, algoritmo genético, self-play paralelo, aptidão 5/2/-1, PGN por geração, versões nomeadas | 2 e 3 | [PR #1](https://github.com/lucas-kiozy/evolutiveChess/pull/1) |

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

**Concluída em 2026-10-07** com o merge do [PR #2](https://github.com/lucas-kiozy/evolutiveChess/pull/2) (pacote `chess_engine/`, Python puro; interface descrita em `chess_engine/API.md`). No `main`, `pytest chess_engine` passa com 97 testes (7 pulados: os lentos e os que comparam com `python-chess`, que precisa estar instalado).

- [x] Representação do tabuleiro e das peças
- [x] Leitura e escrita de posições em FEN, com validação de FEN inválida (inclusive roque sem rei ou torre)
- [x] Geração de lances de todas as peças
- [x] Roque (curto e longo, com todas as restrições)
- [x] Captura *en passant*
- [x] Promoção de peão
- [x] Filtro de lances legais (não deixar o próprio rei em xeque)
- [x] Detecção de xeque, xeque-mate e afogamento
- [x] Empates: repetição tripla e quíntupla, regras dos 50 e 75 lances, material insuficiente
- [x] `play_game` com contagem de lances e de xeques por cor, usada na aptidão da Luna
- [x] Testes de *perft* em 21 posições de referência
- [x] 300 partidas aleatórias comparadas com `python-chess`, sem divergência (406 testes passando)
- [x] Notação algébrica (SAN): `san()`, `parse_san()`, `push_san()`
- [x] Exportação de partidas em PGN (`to_pgn`, `GameResult.pgn`), lida sem erros pelo `python-chess`
- [x] Contadores de `play_game` contam só a própria partida (correção da revisão de código)
- [x] Jogo no terminal: `python -m chess_engine`

### Etapa 2 — Luna: IA evolutiva com algoritmo genético

**Critério de pronto:** uma Luna joga partidas completas usando parâmetros vindos de um genoma, e uma população de Lunas pode ser criada, cruzada e mutada.

**Concluída em 2026-10-07** com o merge do [PR #1](https://github.com/lucas-kiozy/evolutiveChess/pull/1) (pacote `luna/`). Conferido no `main`: `python -m luna train --backend chess_engine` roda uma geração completa. Os testes que usam o backend `python-chess` precisam da biblioteca instalada (`pip install -r luna/requirements.txt`).

- [x] Definir o genoma: 14 pesos de avaliação (`luna/genome.py`)
- [x] Função de avaliação parametrizada pelo genoma (`luna/evaluation.py`)
- [x] Busca de lances: alfa-beta com busca de quiescência (`luna/search.py`)
- [x] Inicialização da população
- [x] Operadores genéticos: seleção por torneio, cruzamento uniforme, mutação gaussiana (`luna/evolution.py`)
- [x] Elitismo (preservar os melhores entre gerações)
- [x] Salvar e carregar gerações com retomada do treino (`luna/storage.py`, pasta `luna/runs/<nome>/`)
- [x] Linha de comando: `python -m luna train` e `python -m luna show`
- [x] Versões nomeadas da Luna: `python -m luna export --name luna-v1` grava `luna/versions/luna-v1.json` (genoma, busca e origem) para ir ao git; `python -m luna versions` lista
- [x] Histórico de evolução por geração (`history.jsonl`)
- [x] Adaptador para o motor próprio (`--backend chess_engine`), testado contra `python-chess`
- [ ] Tornar `chess_engine` o backend padrão (o PR #2 já está no `main`)
- [ ] Exportar a melhor Luna do treino de 600 partidas como `luna-v1` quando o treino terminar
- [x] Velocidade: 7 a 8 s por geração de 8 partidas com o `chess_engine` (8 Lunas, profundidade 2, 4 CPUs)
- [x] Corrigido o ruído na escolha do lance, que fazia a Luna jogar quase ao acaso (apontado na revisão de código)

### Etapa 3 — Self-play paralelo e seleção de descendentes

**Critério de pronto:** uma geração inteira joga em paralelo, a aptidão é calculada pelo critério definido e a próxima geração é gerada automaticamente, em ciclo.

- [x] Partidas Luna contra Luna em paralelo (`ProcessPoolExecutor` em `luna/evolution.py`, partida em `luna/match.py`)
- [x] Alternância de cores: cada par joga duas partidas com cores trocadas (`schedule()` em `luna/evolution.py`)
- [x] Limite de 200 meios-lances por partida, que termina em empate (`MatchConfig.max_plies`)
- [x] Cálculo de aptidão (`luna/fitness.py`):
  - [x] Régua por partida somada na geração: vitória +5, empate +2, derrota -1
  - [x] Desempates: pontos de captura, depois menos xeques nas vitórias, depois menos lances até o mate
- [x] Laço contínuo: jogar → avaliar → selecionar → reproduzir → repetir
- [~] Treino longo e análise dos resultados: um treino de 600 partidas chegou à geração 15 com cerca de 85% a 90% das partidas terminando em mate (arquivos do treino fora do repositório). Num treino curto, depois da correção do ruído, 75% a 88% das partidas terminam em mate, e a melhor Luna dá mate em 25 a 27 lances em média
- [x] Registro das partidas de cada geração em PGN (`generations/gen_NNNN.pgn`, com ids das Lunas, resultado, término e xeques de cada lado)

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

## Decisões tomadas

| Data | Decisão | Por |
|------|---------|-----|
| 2026-10-07 | O primeiro commit (documentação) foi direto no `main`; o resto segue por PR | Lucas |
| 2026-10-07 | Aptidão em partidas sem mate: empate pontua pelo material capturado (peão +0,1, cavalo +0,3, bispo +0,4, torre +0,6, dama +2); cada derrota recebe -5 | Lucas |
| 2026-10-07 | Na derrota, a Luna mantém os pontos do material capturado: derrota = -5 + material | Lucas |
| 2026-10-07 | Régua de aptidão por partida, somada na geração: vitória +5, empate +2, derrota -1 (substitui o -5). Vitória vale sempre mais que empate. Entre vitórias, melhor é a com menos xeques ("ser mais objetivo no ataque"); desempates na ordem: pontos de captura, menos xeques nas vitórias, menos lances até o mate | Lucas |
| 2026-10-07 | Atualizações da documentação vão direto no `main`, sem PR | Lucas |

---

## Decisões em aberto

Pontos que precisam de decisão do Lucas ou da frente responsável antes ou durante a implementação:

1. **Capturas: desempate ou soma.** Na régua 5/2/-1, a frente da Luna deixou os pontos de captura só como desempate, porque somados um empate com muitas capturas (até 7,4) passaria de uma vitória (5). Falta o Lucas confirmar.
2. **Motor de regras próprio ou biblioteca.** Resolvido: o motor próprio (`chess_engine`) está no `main`; `python-chess` fica só como referência nos testes. Falta tornar `chess_engine` o backend padrão da Luna (PR #1).
3. **Como medir "rating equivalente a 1600".** Proposta no PR #4: partidas contra Stockfish com Elo limitado e liberação quando o limite inferior do intervalo de confiança de 90% chegar a 1600. Vira decisão quando o PR for mergeado.
4. **Como a Luna aprende com as partidas do Lichess.** No self-play há uma população inteira; no Lichess joga uma Luna por vez. Falta definir como os resultados online alimentam a evolução.

---

## Histórico de atualizações deste relatório

| Data | O que mudou |
|------|-------------|
| 2026-10-07 | Criação do relatório com as etapas definidas pelo Lucas e o backlog inicial |
| 2026-10-07 | Etapas 2 e 3 em andamento com o PR #1 (Luna); decisão sobre partidas sem mate passa a ser bloqueante |
| 2026-10-07 | Etapa 1 em revisão com o PR #2 (motor de xadrez com todas as regras) |
| 2026-10-07 | Etapas 4 e 5 em revisão com o PR #4 (estimador de rating e bot do Lichess) |
| 2026-10-07 | Lucas decidiu a pontuação de empates e derrotas; seção "Decisões tomadas" criada |
| 2026-10-07 | PR #1 aplicou a nova pontuação e ganhou adaptador para o `chess_engine` |
| 2026-10-07 | Correções da revisão de código: limite de lances, alternância de cores e histórico marcados como `[~]`; FEN e SAN/PGN de volta ao backlog da etapa 1; regra para PRs em revisão explicitada |
| 2026-10-07 | PR #1 corrigiu o ruído na busca: 75% a 88% das partidas agora terminam em mate; nova decisão em aberto sobre número de mates |
| 2026-10-07 | Lucas confirmou que a derrota mantém os pontos de captura |
| 2026-10-07 | PR #2 corrigiu os achados da revisão e ganhou exportação PGN |
| 2026-10-07 | PR #1 passou a gravar as partidas de cada geração em PGN |
| 2026-10-07 | PR #1 ganhou versões nomeadas da Luna; treino de 600 partidas registrado |
| 2026-10-07 | PR #2 mergeado: etapa 1 concluída |
| 2026-10-07 | Lucas definiu a régua 5/2/-1; PR #1 aplicou; decisões em aberto renumeradas |
| 2026-10-07 | PR #1 mergeado: etapas 2 e 3 concluídas |
