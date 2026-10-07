# Relatório de status do projeto

**Última atualização:** 2026-10-07
**Atualizado por:** agente de documentação ([.claude/agents/documentador.md](../.claude/agents/documentador.md))

Este relatório é atualizado depois de cada alteração concluída (PR mergeado) no repositório. Ele mostra o que já foi feito, o que está em andamento e o backlog de cada etapa.

Legenda: `[x]` concluído · `[~]` em andamento · `[ ]` não iniciado

---

## Resumo

| # | Etapa | Status | Progresso |
|---|-------|--------|-----------|
| 0 | Base do projeto (repositório, documentação, frentes de trabalho) | Em andamento | Documentação inicial criada |
| 1 | Jogo de xadrez com regras validadas | Não iniciada | 0% |
| 2 | Luna: IA evolutiva com algoritmo genético | Não iniciada | 0% |
| 3 | Self-play paralelo e seleção de descendentes | Não iniciada | 0% |
| 4 | Medição de rating (meta ~1600) | Não iniciada | 0% |
| 5 | Luna jogando no Lichess | Não iniciada | 0% |

---

## O que já foi feito

| Data | Alteração | Etapa | Referência |
|------|-----------|-------|------------|
| 2026-10-07 | Repositório criado (vazio) | 0 | — |
| 2026-10-07 | README, relatório de status, referências e agente de documentação | 0 | PR de documentação inicial |

---

## Backlog por etapa

### Etapa 0 — Base do projeto

- [x] Criar o repositório `lucas-kiozy/evolutiveChess`
- [~] Documentação inicial: README, relatório de status, referências
- [~] Agente de documentação que atualiza este relatório a cada alteração concluída
- [ ] Definir as frentes (subagentes) de trabalho, no mínimo 3: motor de xadrez, Luna, rating e Lichess
- [ ] Estrutura de pacote Python (`pyproject.toml`, versão mínima do Python, layout `src/`)
- [ ] Ferramentas de qualidade: testes (`pytest`), lint e formatação
- [ ] Integração contínua (GitHub Actions) rodando os testes a cada PR

### Etapa 1 — Jogo de xadrez com regras validadas

**Critério de pronto:** um humano consegue jogar uma partida completa, e todas as regras passam em testes automatizados, incluindo contagem de nós por *perft* em posições de referência.

- [ ] Representação do tabuleiro e das peças
- [ ] Leitura e escrita de posições em FEN
- [ ] Geração de lances de todas as peças
- [ ] Roque (curto e longo, com todas as restrições: rei/torre não movidos, casas livres, sem passar por xeque)
- [ ] Captura *en passant*
- [ ] Promoção de peão (dama, torre, bispo, cavalo)
- [ ] Filtro de lances legais (não deixar o próprio rei em xeque)
- [ ] Detecção de xeque, xeque-mate e afogamento
- [ ] Empates: repetição tripla, regra dos 50 lances, material insuficiente
- [ ] Registro de partidas em notação algébrica (SAN) e exportação em PGN
- [ ] Testes de *perft* contra valores de referência publicados
- [ ] Interface para jogar (terminal, no mínimo)

### Etapa 2 — Luna: IA evolutiva com algoritmo genético

**Critério de pronto:** uma Luna joga partidas completas usando parâmetros vindos de um genoma, e uma população de Lunas pode ser criada, cruzada e mutada.

- [ ] Definir o genoma (por exemplo, pesos de material, posição das peças, mobilidade, segurança do rei, estrutura de peões)
- [ ] Função de avaliação parametrizada pelo genoma
- [ ] Busca de lances (minimax com poda alfa-beta, profundidade configurável)
- [ ] Inicialização da população
- [ ] Operadores genéticos: seleção, cruzamento, mutação
- [ ] Elitismo (preservar os melhores entre gerações)
- [ ] Salvar e carregar genomas e gerações (checkpoints)
- [ ] Histórico de evolução por geração (aptidão média e máxima)

### Etapa 3 — Self-play paralelo e seleção de descendentes

**Critério de pronto:** uma geração inteira joga em paralelo, a aptidão é calculada pelo critério definido e a próxima geração é gerada automaticamente, em ciclo.

- [ ] Torneio entre Lunas (todos contra todos ou pareamento por rodadas)
- [ ] Execução de várias partidas em paralelo (`multiprocessing`/`concurrent.futures`)
- [ ] Alternância de cores (cada par joga de brancas e de pretas)
- [ ] Limite de lances por partida, para evitar partidas infinitas
- [ ] Cálculo de aptidão:
  - [ ] 1º critério: vitória com **menos lances** até o xeque-mate
  - [ ] 2º critério (desempate): **menos xeques** dados durante a partida
- [ ] Laço contínuo: jogar → avaliar → selecionar → reproduzir → repetir
- [ ] Registro das partidas (PGN) e métricas de cada geração

### Etapa 4 — Medição de rating (meta ~1600)

**Critério de pronto:** o rating estimado da melhor Luna é calculado de forma reprodutível, com intervalo de confiança, contra adversários de força conhecida.

- [ ] Escolher adversários de referência com força calibrada (por exemplo, Stockfish com nível ou Elo limitado)
- [ ] Rodar séries de partidas da melhor Luna de cada geração contra esses adversários
- [ ] Estimar o rating (Elo ou Glicko-2) com intervalo de confiança
- [ ] Gatilho: quando o rating estimado atingir ~1600, liberar a etapa 5

### Etapa 5 — Luna jogando no Lichess

**Critério de pronto:** a Luna joga partidas no Lichess por uma conta BOT, uma partida por vez, e continua evoluindo com os resultados.

- [ ] Criar conta BOT no Lichess e token de API (guardado fora do repositório)
- [ ] Integração com a API de bots do Lichess (aceitar desafios, receber o estado da partida, enviar lances)
- [ ] Jogar uma partida por vez, em sequência
- [ ] Usar os resultados das partidas online para continuar a evolução
- [ ] Acompanhar o rating da Luna no Lichess ao longo do tempo

---

## Decisões em aberto

Pontos que precisam de decisão do Lucas ou da frente responsável antes ou durante a implementação:

1. **Partidas empatadas no cálculo de aptidão.** O critério atual cobra vitórias (menos lances até o mate) com desempate por menos xeques. Ainda não está definido quanto vale um empate (afogamento, repetição, 50 lances, material insuficiente) nem uma partida interrompida pelo limite de lances.
2. **Pontuação de derrotas.** Se uma Luna perde, ela recebe aptidão zero ou ganha algo por ter resistido mais lances?
3. **Motor de regras próprio ou biblioteca.** Implementar as regras do zero ou usar uma biblioteca consolidada como [`python-chess`](https://python-chess.readthedocs.io/) como referência de validação.
4. **Como medir "rating equivalente a 1600".** Rating Elo/Glicko contra quais adversários de referência, com quantas partidas.

---

## Histórico de atualizações deste relatório

| Data | O que mudou |
|------|-------------|
| 2026-10-07 | Criação do relatório com as etapas definidas pelo Lucas e o backlog inicial |
