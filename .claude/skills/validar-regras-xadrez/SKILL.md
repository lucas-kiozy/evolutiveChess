---
name: validar-regras-xadrez
description: Confere se lances de xadrez são legais numa posição (FEN ou sequência a partir do início) usando o motor chess_engine do evolutiveChess, explica por que um lance é ilegal e diz se há xeque, mate, afogamento, roque, en passant, promoção ou empate. Use sempre que perguntarem se um lance pode, por que o motor recusou um lance, se uma posição é mate, para listar lances legais, conferir uma FEN, ou suspeitarem de bug nas regras do motor, mesmo sem citar FEN.
---

# Validar regras de xadrez

O motor do projeto (`chess_engine/`, interface em `chess_engine/API.md`) já
implementa todas as regras e é testado contra perft de referência e contra o
python-chess. Responda com base nele, rodando o script abaixo, em vez de
raciocinar de cabeça sobre a posição: é fácil errar casas atacadas, cravadas
e direitos de roque olhando só a FEN. Não edite `chess_engine/`; se achar um
bug, mostre a divergência e diga que a correção é da frente do motor.

Rode da raiz do repositório:

```bash
python .claude/skills/validar-regras-xadrez/scripts/validar.py --fen "<FEN>" --lances "<lances>" [--listar] [--cruzar] [--json]
```

- `--fen`: posição; sem ela, parte da posição inicial.
- `--lances`: um ou mais lances separados por espaço, em UCI (`e1g1`, `e7e8q`)
  ou SAN (`O-O`, `Nbd2`, `exd6`, `e8=Q`). Números de lance como `1.` são
  ignorados, então dá para colar um trecho de PGN. São aplicados em
  sequência; o primeiro ilegal para a sequência e vem com o motivo.
- `--listar`: lista os lances legais da posição final em SAN.
- `--cruzar`: confere lances legais, xeque e mate com o python-chess. Use
  quando o usuário suspeitar de bug no motor. Se o python-chess não estiver
  instalado, `pip install chess` (num venv, se o pip do sistema falhar).
- O código de saída é 1 se a FEN for inválida ou algum lance for ilegal.

## Como responder

Comece pelo veredito (legal ou ilegal) e pelo motivo em uma frase, nos termos
do usuário: "Não pode rocar: o rei passaria por f1, atacada pelo bispo de c4".
Depois, só o que ajuda: o lance em SAN, se dá xeque ou mate, e a FEN
resultante se ele for continuar dali. Quando o script disser que a
FEN foi rejeitada, explique o problema (ex.: peão na 8ª fileira, lado que não
joga em xeque) em vez de só repetir o erro.

Os motivos do script cobrem: casa de origem vazia, peça do adversário, casa
ocupada por peça própria, roque sem direito, bloqueado, em xeque ou passando
por casa atacada, promoção faltando ou indevida e lance que deixaria o
próprio rei em xeque (este último só é identificado com o python-chess
instalado; sem ele, o script dá um motivo mais genérico).

Empates por 50 lances e repetição tripla são reivindicáveis (a partida só
acaba se um jogador pedir); 75 lances, repetição quíntupla, afogamento e
material insuficiente encerram sozinhos. O script separa os dois casos.
