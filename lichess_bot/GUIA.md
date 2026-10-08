# Luna no Lichess

Integração pela [Bot API oficial](https://lichess.org/api#tag/Bot). A Luna joga
**uma partida por vez**: enquanto joga, recusa novos desafios com o motivo
"later". Ao fim de cada partida, o registro completo vai para o aprendiz.

Nada aqui joga sozinho. Você roda o comando quando quiser.

## O que você (Lucas) precisa fazer, quando a Luna chegar a ~1600

1. **Criar uma conta nova no Lichess só para a Luna** (ex.: `LunaEvolutiva`).
   Ela não pode ter jogado nenhuma partida, e o upgrade para BOT é
   **irreversível**: a conta passa a jogar só como bot. Não use sua conta pessoal.
2. Logado nessa conta nova, criar um token com a permissão
   **"Play games with the bot API" (`bot:play`)**:
   https://lichess.org/account/oauth/token/create?scopes[]=bot:play
3. Guardar o token só em variável de ambiente, nunca no repositório:
   ```bash
   export LICHESS_BOT_TOKEN=lip_xxxxxxxx
   ```
4. Conferir e converter a conta:
   ```bash
   pip install -r lichess_bot/requirements.txt
   python -m lichess_bot check             # mostra a conta e se já é BOT
   python -m lichess_bot upgrade --confirm # irreversível
   ```
5. Colocar a Luna para jogar:
   ```bash
   python -m lichess_bot play --player luna_player:luna_factory
   # opções: --max-games 10  --casual-only  --matchmaking
   ```

Se o token vazar, revogue em https://lichess.org/account/oauth/token.

## Como as partidas chegam

- Bots não entram no pareamento automático do Lichess. A Luna joga quando
  alguém a desafia ou, com `--matchmaking`, desafia outro bot online de rating
  próximo depois de 2 minutos ociosa.
- Desafios aceitos por padrão: xadrez padrão, ritmo rápido ou clássico, com
  relógio de pelo menos 1500 s contando base + 60 × incremento (ex.: 25+0,
  15+10, 30+20; 10+5 é recusado), até 3 h de base e 60 s de incremento,
  valendo ou não rating. Bullet, blitz, correspondência e variantes são
  recusados. O matchmaking desafia em 30+20. Ajuste em `lichess_bot/config.py`.
- Se o adversário abandona a partida, o bot reivindica a vitória quando o
  Lichess permite.

## Ritmo dos lances (pedido do Lucas)

Contra pessoas e outros bots no Lichess, cada lance da Luna leva, no total
(pensando + esperando):

| Lance da Luna | Tempo |
|---|---|
| 1 a 6 | 20 s |
| 7 a 40 | 1 + X s, X inteiro aleatório de 0 a 15 |
| 41 em diante | Y s, Y inteiro aleatório de 16 a 90 |

Por que 1500 s de relógio: numa partida média de 60 lances da Luna o ritmo
gasta ~1470 s (6×20 + 34×8,5 + 20×53). Se o relógio apertar, a espera nunca
passa de 8% do tempo restante mais 90% do incremento, então a Luna acelera em
vez de perder por tempo. `--no-pacing` desliga o ritmo. Treino e medição de
rating não esperam nada.

## Desistência

- **A Luna desiste** quando a avaliação dela fica em -1000 centipeões ou menos
  (ou mate contra ela) por 3 lances seguidos dela, o mesmo padrão do
  lichess-bot (`resign_score: -1000`, `resign_moves: 3`), **e** ela não
  enxerga nenhum empate forçado. Antes de desistir, ela procura, em até 8
  meios-lances a partir da posição real (com o histórico), um caminho que force
  afogamento, material insuficiente, repetição tripla, regra dos 50 lances ou
  xeque perpétuo. Se achar, ou se a busca não chegar a uma conclusão, continua
  jogando. A regra está em `rating/resign.py`, e a aba Jogar do tabuleiro usa o
  mesmo critério. A avaliação vem de `LunaPlayer.last_score`; num jogador sem
  esse atributo, o material serve de aproximação (10 pontos atrás ≈ -1000 cp).
- **Quando o adversário desiste**, a partida termina com vitória da Luna:
  1 ponto, como qualquer vitória (`GameRecord.luna_won_by_resignation`).

## Aprendizado contínuo

Cada partida terminada vira um `GameRecord` (lances em UCI, PGN, resultado,
ratings, quantos lances a Luna fez, xeques dados e recebidos, se alguém
desistiu) e é:

1. gravada em `lichess_bot/runs/games.jsonl` e `games.pgn`;
2. entregue ao aprendiz passado em `--learner modulo:fabrica`, se houver.

O aprendiz é qualquer objeto com `on_game_finished(record)`; a fábrica recebe
a pasta de dados. É ali que a frente da Luna decide como evoluir com as
partidas reais (por exemplo, usar os resultados como aptidão de uma geração).

## Regras da API que o cliente respeita

- Uma requisição por vez; ao receber HTTP 429, espera um minuto.
- Streams ND-JSON: linhas vazias são keep-alive e são ignoradas.
- O upgrade para BOT só acontece com `--confirm` explícito.
