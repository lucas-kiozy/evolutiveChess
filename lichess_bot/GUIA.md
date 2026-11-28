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
   python -m lichess_bot play --player luna.player:lichess_factory
   # opções: --max-games 10  --casual-only  --matchmaking
   ```
   `lichess_factory` é a Luna oficial (`luna/versions/oficial.txt`) com três
   ajustes para jogar contra pessoas (decisões do Lucas em 2026-11-27): abre
   sempre 1.e4 de brancas e 1...c6 de pretas, sorteia entre lances que diferem
   até 5 centipeões (`LUNA_NOISE=0` desliga) e segue o relógio da partida.

Se o token vazar, revogue em https://lichess.org/account/oauth/token.

## Como as partidas chegam

- Bots não entram no pareamento automático do Lichess. A Luna joga quando
  alguém a desafia ou, com `--matchmaking`, desafia outro bot online de rating
  próximo depois de 2 minutos ociosa.
- Com `--matchmaking`, o desafio automático é **15+5** (decisão do Lucas em
  2026-11-27), ritmo em que cabe o teto de 20 s por lance da Luna.
- Desafios aceitos por padrão: xadrez padrão, com relógio, de 3 a 30 minutos de
  base e até 30 s de incremento, valendo ou não rating. Correspondência e
  variantes são recusadas. Ajuste em `lichess_bot/config.py`.
- Se o adversário abandona a partida, o bot reivindica a vitória quando o
  Lichess permite.

## Tempo por lance

A Luna usa o orçamento de tempo das partidas oficiais (`luna.search.TimeBudget`):
teto normal de 20 s por lance, parada antecipada quando o melhor lance é estável
e até 5 lances por partida estendidos até 40 s, só quando a busca está instável.
O bot passa o relógio a cada lance (`set_clock`), e os tetos encolhem para caber
nele: o teto normal vira `restante / 25 + 3/4 do incremento` e o estendido no
máximo `restante / 8`. Em 15+5, mesmo gastando o teto em todo lance, a Luna
mantém os 20 s até por volta do lance 30 e não perde no tempo. Variáveis:
`LUNA_TIME_LIMIT` (teto normal; 0 desliga), `LUNA_EXTENDED_TIME` e
`LUNA_EXTENSIONS`.

## Aprendizado contínuo

Cada partida terminada vira um `GameRecord` (lances em UCI, PGN, resultado,
ratings, quantos lances a Luna fez, xeques dados e recebidos) e é:

1. gravada em `lichess_bot/runs/games.jsonl` e `games.pgn`;
2. entregue ao aprendiz passado em `--learner modulo:fabrica`, se houver.

O aprendiz é qualquer objeto com `on_game_finished(record)`; a fábrica recebe
a pasta de dados. É ali que a frente da Luna decide como evoluir com as
partidas reais (por exemplo, usar os resultados como aptidão de uma geração).

## Regras da API que o cliente respeita

- Uma requisição por vez; ao receber HTTP 429, espera um minuto.
- Streams ND-JSON: linhas vazias são keep-alive e são ignoradas.
- O upgrade para BOT só acontece com `--confirm` explícito.
