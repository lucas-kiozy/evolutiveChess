---
name: relatorio-evolucao-luna
description: Gera o relatório de evolução da Luna (IA evolutiva do evolutiveChess) a partir do histórico de gerações, com tendência de mates, tabela por geração, genes que mais mudaram, gráfico e Elo relativo medido em partidas entre gerações. Use sempre que perguntarem se a Luna está melhorando, como foi o treino, quanto ela evoluiu, para comparar gerações, ver o Elo ou um gráfico do progresso, mesmo que só perguntem "como está a IA?".
---

# Relatório de evolução da Luna

O histórico do treino fica em `luna/runs/<treino>/` (`history.jsonl` e
`generations/gen_NNNN.json`, ver `luna/storage.py`). O script abaixo lê esses
arquivos com o código da Luna e usa o estimador de Elo de `rating/elo.py`;
não reimplemente nada disso e não edite `luna/`, `rating/`, `docs/` nem o README.

Rode da raiz do repositório:

```bash
python .claude/skills/relatorio-evolucao-luna/scripts/relatorio.py --run-dir luna/runs/default
```

Opções:
- `--elo`: mede força de verdade. O melhor genoma de algumas gerações
  (`--checkpoints`, padrão 4) joga `--partidas` (padrão 20, cores
  alternadas) contra o melhor da 1ª geração, e o Elo relativo sai por máxima
  verossimilhança no modelo de Elo/Bradley-Terry, com erro-padrão.
- `--ancora referencia`: usa como adversário fixo o genoma de referência
  (os pesos iniciais, `Genome.reference()`) em vez do melhor da 1ª geração,
  e mede também a 1ª geração. Responde "os genes evoluídos já superam os
  pesos de partida?", útil quando a 1ª geração já é aleatória e fraca.
- `--grafico arquivo.png`: taxa de mate, lances até o mate e, com `--elo`, o
  Elo com intervalo de 95%. Precisa de matplotlib.
- `--saida relatorio.md`: grava o relatório em Markdown.
- `--json`: saída estruturada, se for processar os números (com `--saida`, o
  Markdown também é gravado).

Se o usuário não disse qual treino, use `luna/runs/default`; se ela não
existir, liste `luna/runs/` e use a pasta com mais gerações, dizendo qual.

## Quando usar `--elo`

As métricas do histórico vêm de partidas da população contra ela mesma. Se
todos melhoram juntos, a taxa de mate pode ficar parada, e se todos pioram,
pode subir. Por isso, quando a pergunta é "ela está ficando mais forte?",
rode com `--elo`. Antes, estime o custo: são `(checkpoints − 1) × partidas`
partidas na profundidade do treino. Com mais partidas o erro cai devagar
(cerca de 55 Elo de erro-padrão com 40 partidas; ver `rating.elo.games_needed`).

## Como responder

Abra com a resposta direta: está melhorando, estável ou piorando, e a
evidência (ex.: "+120 ± 45 Elo da geração 1 para a 30, em 20 partidas").
Diga se a diferença é estatisticamente clara: o script indica quando o
intervalo de 95% exclui zero. Se houver poucas gerações ou poucas partidas,
diga que a conclusão é provisória. Entregue a tabela e o gráfico como
arquivos quando forem grandes, em vez de colar tudo.

O Elo aqui é relativo ao próprio treino e não se compara ao Lichess nem à
FIDE. Para rating absoluto contra o Stockfish calibrado existe
`python -m rating` (veja `rating/GUIA.md`), que precisa do Stockfish instalado.
