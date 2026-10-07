---
name: luna-treino
description: Treina a Luna, a IA de xadrez evolutiva do evolutiveChess, rodando novas gerações de partidas IA contra IA com seleção, cruzamento e mutação (python -m luna train). Use sempre que pedirem para treinar, evoluir, rodar mais gerações ou partidas de self-play, retomar ou começar um treino, ajustar população, mutação ou profundidade, ou perguntarem quanto tempo um treino leva, mesmo que não digam "Luna" nem "algoritmo genético".
---

# Treinar a Luna

A Luna evolui os pesos da sua função de avaliação por algoritmo genético em
self-play, como em David, Koppel e Netanyahu (2014, *IEEE Trans. Evolutionary
Computation*): a busca alfa-beta fica fixa e só os genes (valores das peças,
mobilidade, estrutura de peões etc.) mudam. Todo o treino já está em `luna/`;
esta skill só diz como usá-lo bem. Não reimplemente treino, aptidão nem
partidas, e não edite `luna/`, `chess_engine/`, `rating/`, `docs/` nem o
README: mudanças nesses pacotes são das frentes donas deles.

Rode tudo da raiz do repositório. Se `import chess` falhar, instale com
`pip install -r luna/requirements.txt` (em Debian/Ubuntu com erro de
`install_layout`, crie antes um venv: `python3 -m venv .venv && . .venv/bin/activate`).

## Passo a passo

1. **Veja o estado atual** antes de treinar:
   ```bash
   python .claude/skills/luna-treino/scripts/resumo_treino.py --run-dir luna/runs/default --estimar <N>
   ```
   Mostra quantas gerações já existem, a configuração salva e o tempo
   estimado para mais N gerações pelo ritmo medido.

2. **Escolha a pasta do treino.** `--run-dir` identifica um treino. Se a pasta
   já tem treino, `train` **retoma** de onde parou e **ignora** os parâmetros
   passados na linha de comando: vale a configuração salva em `config.json`.
   Para testar outros parâmetros (população, profundidade, mutação), use uma
   pasta nova, por exemplo `luna/runs/pop32-d3`, e diga isso ao usuário.
   Num treino novo feito para comparar com outro, copie do `config.json` do
   treino de referência tudo o que o usuário não pediu para mudar (por
   exemplo `--max-plies`, `--rounds`, `--seed`): os padrões da linha de
   comando podem ser diferentes dos que o treino de referência usou, e aí a
   comparação mistura duas mudanças.

3. **Meça antes de um treino longo.** Sem histórico, rode 1 geração primeiro e
   use o tempo dela para estimar o resto. O custo cresce com população ×
   rodadas × profundidade; profundidade 3 em diante é bem mais lenta que 2.

4. **Treine:**
   ```bash
   python -m luna train --run-dir luna/runs/default --generations 10
   ```
   Parâmetros úteis num treino novo: `--population` (par), `--elite`,
   `--rounds`, `--mutation-rate`, `--mutation-scale`, `--depth`,
   `--max-plies`, `--backend python-chess|chess_engine`, `--fallback
   captures|pure`, `--workers` (0 = todas as CPUs), `--seed`. Se a estimativa
   passar de alguns minutos, rode em segundo plano e acompanhe a saída;
   cada geração é salva ao terminar, então interromper não perde o que já foi feito.

5. **Resuma o resultado** rodando o `resumo_treino.py` de novo e conte ao
   usuário, em poucas linhas: gerações rodadas, taxa de mate, mate médio do
   melhor, tempo gasto e o que mudou nos genes. Para saber se a IA ficou
   *mais forte*, sugira a skill `relatorio-evolucao-luna` com `--elo`.

## Como a aptidão funciona (definida pelo Lucas)

Está em `luna/fitness.py`. Entre as Lunas que deram mate, a melhor é a que
precisou de menos lances, com desempate por menos xeques dados. As que não
deram mate são ordenadas pela pontuação de capturas em empates e derrotas
(peão 0,1, cavalo 0,3, bispo 0,4, torre 0,6, dama 2; derrota −5), ou só por
xeques com `--fallback pure`. Se o usuário quiser mudar o critério, isso é
mudança em `luna/`: diga que precisa ser feita pela frente da Luna.

## Cuidados

- Os resultados ficam em `luna/runs/`, que não vai para o git.
- Treinos com o mesmo `--seed` e a mesma configuração se repetem; mude o seed
  para uma réplica independente.
- Self-play mede a população contra ela mesma. Taxa de mate subindo não prova
  que a Luna ficou mais forte; o Elo relativo do relatório responde isso.
