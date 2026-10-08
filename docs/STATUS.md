# Relatório de status do projeto

**Última atualização:** 2026-10-08
**Atualizado por:** agente de documentação ([.claude/agents/documentador.md](../.claude/agents/documentador.md))

Este relatório é atualizado depois de cada alteração concluída no repositório. Itens de PRs ainda em revisão aparecem como `[~]` e só passam a `[x]` quando o PR é mergeado no `main`.

**Último commit do `main` coberto:** `1274549`

Legenda: `[x]` concluído no `main` · `[~]` em andamento ou em PR aberto · `[ ]` não iniciado

---

## Resumo

| # | Etapa | Status | Progresso |
|---|-------|--------|-----------|
| 0 | Base do projeto (repositório, documentação, frentes de trabalho) | **Concluída** | Pacote, testes e CI no `main` pelo [PR #5](https://github.com/lucas-kiozy/evolutiveChess/pull/5); falta só o lint bloqueante |
| 1 | Jogo de xadrez com regras validadas | **Concluída** | Motor mergeado no `main` pelo [PR #2](https://github.com/lucas-kiozy/evolutiveChess/pull/2) |
| 2 | Luna: IA evolutiva com algoritmo genético | **Concluída** | Luna no `main` pelo [PR #1](https://github.com/lucas-kiozy/evolutiveChess/pull/1); faltam ajustes (backend padrão, versão `luna-v1`) |
| 3 | Self-play paralelo e seleção de descendentes | **Concluída** | Laço no `main` pelo [PR #1](https://github.com/lucas-kiozy/evolutiveChess/pull/1); o primeiro treino de 600 partidas não mostrou evolução consistente |
| 4 | Medição de rating (meta ~1600) | Em andamento | Melhor medição até agora: 1324 ± 45 (antes 1216 ± 47); meta 1600 |
| 5 | Luna jogando no Lichess | Em andamento | Bot no `main` pelo [PR #4](https://github.com/lucas-kiozy/evolutiveChess/pull/4); falta a Luna chegar a ~1600, a conta BOT e o aprendizado online |

---

## O que já foi feito

| Data | Alteração | Etapa | Referência |
|------|-----------|-------|------------|
| 2026-10-07 | Repositório criado (vazio) | 0 | — |
| 2026-10-07 | README, relatório de status, referências e agente de documentação | 0 | Primeiro commit do `main` |
| 2026-10-07 | Motor de xadrez com todas as regras, FEN, SAN, PGN e jogo no terminal | 1 | [PR #2](https://github.com/lucas-kiozy/evolutiveChess/pull/2) |
| 2026-10-07 | Luna: genoma, avaliação, busca alfa-beta, algoritmo genético, self-play paralelo, aptidão 5/2/-1, PGN por geração, versões nomeadas | 2 e 3 | [PR #1](https://github.com/lucas-kiozy/evolutiveChess/pull/1) |
| 2026-10-07 | Estimativa de rating contra Stockfish e bot do Lichess pela Bot API oficial | 4 e 5 | [PR #4](https://github.com/lucas-kiozy/evolutiveChess/pull/4) |
| 2026-10-07 | `pyproject.toml`, CI no GitHub Actions e plano de base e integração (`plans/`) | 0 | [PR #5](https://github.com/lucas-kiozy/evolutiveChess/pull/5) |
| 2026-10-07 | Skills `luna-treino`, `validar-regras-xadrez` e `relatorio-evolucao-luna` | 0 | [PR #6](https://github.com/lucas-kiozy/evolutiveChess/pull/6) |
| 2026-10-07 | Primeira versão nomeada da Luna (`luna-v1`), ponto de comparação para os próximos treinos | 3 | [PR #7](https://github.com/lucas-kiozy/evolutiveChess/pull/7) |
| 2026-10-07 | Comparador de velocidade entre os backends | 2 | [PR #8](https://github.com/lucas-kiozy/evolutiveChess/pull/8) |
| 2026-10-07 | `chess_engine` como backend padrão da Luna; avisos do lint limpos em `luna/` | 2 | [PR #9](https://github.com/lucas-kiozy/evolutiveChess/pull/9) |
| 2026-10-07 | Menos ruído na seleção: 18 partidas por Luna, elite com resultados acumulados, partidas contra campeãs passadas | 3 | [PR #10](https://github.com/lucas-kiozy/evolutiveChess/pull/10) |

---

## Backlog por etapa

### Etapa 0 — Base do projeto

- [x] Criar o repositório `lucas-kiozy/evolutiveChess`
- [x] Documentação inicial: README, relatório de status, referências
- [x] Agente de documentação que atualiza este relatório a cada alteração concluída
- [x] Frentes de trabalho (no mínimo 3): motor de xadrez, Luna, rating e Lichess, cada uma numa conversa do projeto
- [x] Pacote Python na raiz (`pyproject.toml`, Python 3.10 ou mais novo; `pip install -e ".[dev]"`) — [PR #5](https://github.com/lucas-kiozy/evolutiveChess/pull/5)
- [x] Testes com `pytest` cobrindo os quatro pacotes — PR #5
- [x] Integração contínua no GitHub Actions: testes em Python 3.10 a 3.13 a cada PR, lint e perft profundo no `main` — PR #5
- [x] Skills do Claude para treinar a Luna, validar regras e relatar a evolução (`.claude/skills/`) — [PR #6](https://github.com/lucas-kiozy/evolutiveChess/pull/6)
- [ ] Tornar o lint (`ruff`) bloqueante: hoje ele roda mas não reprova, porque o código ainda tem avisos (o PR #9 limpa os avisos em `luna/`)

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

**Concluída em 2026-10-07** com o merge do [PR #1](https://github.com/lucas-kiozy/evolutiveChess/pull/1) (pacote `luna/`). Conferido no `main`: `python -m luna train --backend chess_engine` roda uma geração completa, e os testes de todos os pacotes passam (232 passaram, 7 pulados por serem lentos), com `python-chess` instalado.

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
- [x] `chess_engine` é o backend padrão da Luna, com partidas idênticas nos dois backends — [PR #9](https://github.com/lucas-kiozy/evolutiveChess/pull/9)
- [x] Melhor Luna do treino de 600 partidas exportada como `luna-v1` (arquivo na pasta compartilhada do projeto, `luna-treinos/versoes/luna-v1.json`)
- [x] `luna-v1.json` em `luna/versions/` no repositório, como ponto de comparação — [PR #7](https://github.com/lucas-kiozy/evolutiveChess/pull/7)
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
- [x] Primeiro treino longo: 600 partidas (20 Lunas, 15 gerações, profundidade 2, motor próprio), com 78% a 95% de mates por geração. Usou a aptidão antiga, não a régua 5/2/-1
- [x] Análise da evolução, em confrontos de 40 partidas: a `luna-v1` perde para os pesos iniciais (-108 ± 58 Elo), empata com a melhor da geração 1 (-9 ± 55) e vence a da geração 8 (+98 ± 57). **Não houve evolução consistente.** Causa provável: cada Luna joga só 4 partidas por geração, e a ordem antiga favorecia o mate rápido mesmo com mais derrotas (a campeã teve 1 vitória e 2 derrotas), então a seleção ficou quase aleatória
- [x] Reduzir o ruído na seleção: 18 partidas por Luna em cada geração (`--games-per-luna`), a elite carrega os resultados das gerações anteriores (ranking pela média por partida) e cada Luna enfrenta 2 campeãs passadas (`--hall-of-fame`). Custo: cerca de 70 s por geração com 8 Lunas, profundidade 2, 4 CPUs — [PR #10](https://github.com/lucas-kiozy/evolutiveChess/pull/10)
- [x] Segundo treino, com a régua 5/2/-1: 12 gerações e 2.580 partidas (20 Lunas, 18 partidas cada, 2 campeãs passadas), partindo da população do treino de 600. Mates por geração: 86% a 93%
- [x] Análise, em confrontos de 40 partidas: a nova melhor Luna (`g0012-i10`) empata com a `luna-v1` (21/40, +17 ± 55 Elo) e com as melhores das gerações 1 e 6 (21/40 cada), e fica um pouco atrás dos pesos iniciais (17/40, -53 ± 56). **Nenhuma diferença é estatisticamente significativa: a evolução ainda não aparece com clareza**
- [x] Mais 20 gerações do mesmo treino (13 a 32, 4.400 partidas; 7.000 no total), com 81% a 91% de mates por geração
- [x] Análise: a melhor da geração 32 (`g0032-i07`) vence a `luna-v1` (25/40, +89 ± 57 Elo) e a melhor da geração 12 (23/40, +53 ± 56), empata com a da geração 22 (21/40) e segue atrás dos pesos iniciais (17/40, -53 ± 56). **Primeiro sinal de progresso no confronto direto**, mas ainda dentro de cerca de 1,6 erro-padrão
- [ ] Entender por que os pesos iniciais continuam à frente e definir os próximos ajustes do treino
- [x] Comparador de velocidade entre os backends (`tools/bench_backends.py`): o motor próprio ficou cerca de 1,8 vez mais rápido que o `python-chess` — [PR #8](https://github.com/lucas-kiozy/evolutiveChess/pull/8)
- [x] Registro das partidas de cada geração em PGN (`generations/gen_NNNN.pgn`, com ids das Lunas, resultado, término e xeques de cada lado)

### Etapa 4 — Medição de rating (meta ~1600)

**Critério de pronto:** o rating estimado da melhor Luna é calculado de forma reprodutível, com intervalo de confiança, contra adversários de força conhecida.

No `main` desde 2026-10-07 pelo [PR #4](https://github.com/lucas-kiozy/evolutiveChess/pull/4) (pacote `rating/`, guia em `rating/GUIA.md`). Precisa do Stockfish instalado na máquina.

- [x] Adversário de referência: Stockfish com `UCI_Elo` calibrado (piso de 1320, o mínimo do Stockfish)
- [x] Séries de partidas em paralelo contra esse adversário
- [x] Estimativa do rating por máxima verossimilhança no modelo de Elo, com intervalo de confiança de 90%
- [x] Critério "pronta para o Lichess": limite inferior do IC 90% maior ou igual a 1600
- [x] Interface comum de jogador: `choose_move(fen, lances_uci) -> uci`
- [x] Primeira medição, da `luna-v1`: 60 partidas contra Stockfish 16 com Elo limitado (12 vitórias, 18 empates, 30 derrotas, 35% dos pontos). Estimativa de 1216 ± 47 (IC 90%: 1139 a 1293) na escala CCRL/UCI_Elo. Como o intervalo inteiro fica abaixo de 1320, o piso do Stockfish, a conclusão firme é "abaixo de ~1320". Essa escala não é a do Lichess
- [x] Segunda medição, da melhor Luna do treino com a régua nova (`g0012-i10`): 60 partidas contra Stockfish 16 (20 vitórias, 13 empates, 27 derrotas, 44% dos pontos). Estimativa de 1324 ± 45 (IC 90%: 1250 a 1399), cerca de 108 pontos acima da `luna-v1`. A diferença é de cerca de 1,7 erro-padrão: indício de melhora, não prova, e o rating fica em torno do piso de ~1320
- [x] Terceira medição, da melhor Luna da geração 32: 60 partidas contra Stockfish 16 (20 vitórias, 16 empates, 24 derrotas, 47% dos pontos). Estimativa de 1300 ± 45 (IC 90%: 1226 a 1373), igual, dentro da margem, aos 1324 ± 45 da geração 12
- [ ] Medir a melhor Luna de cada novo treino até chegar a ~1600

### Etapa 5 — Luna jogando no Lichess

**Critério de pronto:** a Luna joga partidas no Lichess por uma conta BOT, uma partida por vez, e continua evoluindo com os resultados.

No `main` desde 2026-10-07 pelo [PR #4](https://github.com/lucas-kiozy/evolutiveChess/pull/4) (pacote `lichess_bot/`, guia em `lichess_bot/GUIA.md`).

- [x] Integração com a Bot API oficial do Lichess
- [x] Uma partida por vez, em sequência
- [x] Cada partida gravada em `lichess_bot/runs/`, com gancho `on_game_finished` para o aprendizado
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
| 2026-10-07 | Pontos de captura ficam só como desempate na régua 5/2/-1 (somados, um empate com muitas capturas passaria de uma vitória) | Lucas, ao mergear o PR #1 |
| 2026-10-07 | Motor de regras próprio (`chess_engine`); `python-chess` fica só como referência nos testes e como backend alternativo | Lucas, ao mergear o PR #2 |
| 2026-10-07 | Atualizações da documentação vão direto no `main`, sem PR | Lucas |
| 2026-10-07 | Próximo treino: 18 partidas por Luna por geração, pontuação acumulada da elite, partidas contra campeãs passadas, mais 12 gerações e novo teste de rating | Lucas |
| 2026-10-07 | "Rating 1600" = partidas contra Stockfish com Elo limitado; a Luna está pronta para o Lichess quando o limite inferior do intervalo de confiança de 90% chegar a 1600 | Lucas, ao mergear o PR #4 |

---

## Decisões em aberto

Pontos que precisam de decisão do Lucas ou da frente responsável antes ou durante a implementação:

1. **Como a Luna aprende com as partidas do Lichess.** No self-play há uma população inteira; no Lichess joga uma Luna por vez. Falta definir como os resultados online alimentam a evolução.

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
| 2026-10-07 | PR #4 mergeado: ferramentas das etapas 4 e 5 no `main` |
| 2026-10-07 | PR #5 mergeado: etapa 0 concluída (pacote, testes e CI) |
| 2026-10-07 | PR #6 mergeado: skills do Claude registradas |
| 2026-10-07 | Resultados do treino de 600 partidas e da primeira medição de rating (`luna-v1` abaixo de ~1320) |
| 2026-10-07 | PR #7 mergeado: versão `luna-v1` no repositório |
| 2026-10-07 | PR #9 aberto: `chess_engine` como backend padrão da Luna |
| 2026-10-07 | Plano do próximo treino registrado; PR #8 (comparador de velocidade) aberto; decisão sobre capturas encerrada |
| 2026-10-07 | PRs #8, #9 e #10 mergeados (246 testes passando no `main`) |
| 2026-10-07 | Resultado do segundo treino (régua 5/2/-1, 2.580 partidas) e segunda medição de rating (1324 ± 45) |
| 2026-10-08 | Gerações 13 a 32 do treino com a régua nova e terceira medição de rating (1300 ± 45) |
