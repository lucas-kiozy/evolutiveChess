# Catraca de promoção: protocolo pré-registrado

**Versão do protocolo:** `2026-11-28` (constante `PROTOCOL` em `luna/promotion.py`, gravada em todo resultado)
**Origem:** revisão do algoritmo genético por quatro especialistas e um revisor por pares em 2026-11-28, aprovada pelo Lucas (síntese em `revisoes/especialistas-ag-2026-11-28/` nos arquivos do projeto).

Uma Luna só vira a oficial vencendo a oficial atual neste teste. As regras abaixo são fixadas **antes** de cada desafio e não mudam durante ele. Se uma regra precisar mudar, ela vale só para os desafios seguintes, com uma versão nova do protocolo.

## Regras

1. **Condições oficiais**: escala 2/4/5 por lance, +4 meios-lances extras quando sobra tempo, orçamento de 20 s (40 s nos lances estendidos), sem ruído na raiz (`official_search`).
2. **Pares**: mesma abertura do livro (`luna/openings.py`) e os mesmos 2 lances aleatórios nas duas partidas do par, cores trocadas.
3. **Semente nova por desafio**: a semente vem dos nomes da candidata e da oficial (`challenge_seed`). Antes era sempre 2026, e todo desafio rejogava os mesmos pares (Dwork et al. 2015, *Science* 349:636-638, sobre reusar o conjunto de teste).
4. **Teste sequencial** (Wald 1945): H0 = 0 Elo, H1 = +30 Elo, alfa = beta = 5%, pelo menos 16 pares antes de parar, variância com um pseudo-par em cada resultado possível. Teto de 2.000 partidas: sem decisão, a candidata não é promovida.
5. **Confirmação**: depois de um H1, um segundo teste igual, com pares novos (semente `...-confirmacao`), também precisa dar H1. Isso controla os desafios repetidos contra a mesma oficial: com 4 desafios (g13, g19, g32 e g45 contra a `luna-v4`), o risco de alguma promoção falsa chegava a ~10% a 15%. Com a confirmação, cada desafio tem alfa de ~0,25% e o poder em +30 Elo fica em ~90%.
6. **Elo relatado**: além do Elo estimado, o resultado traz `elo_corrigido`, corrigido pelo viés da parada do teste sequencial (Whitehead 1986, *Biometrika* 73:573-581). Na simulação da revisão, candidatas promovidas com Elo verdadeiro de +10 a +25 mediam em média +34 a +38.
7. **Pré-seleção separada**: quando há várias candidatas, cada uma joga 32 partidas (`--fixo`); a de mais pontos faz o desafio com `--offset 1000`, isto é, com pares que a pré-seleção não jogou. O placar da pré-seleção não entra no teste (maldição do vencedor: a g45 fez +100 ± 62 na pré-seleção e +25 ± 10 no teste).
8. **Retomável**: `--out PASTA` grava cada lote em `pares.jsonl` (e `pares-confirmacao.jsonl`); rodar de novo continua com as mesmas sementes.

## Como rodar

```bash
# Uma candidata
python -m luna promote --candidate luna/versions/candidata.json --name luna-v6 --out desafios/luna-v6

# Várias candidatas: pré-seleção + desafio, retomável
tools/catraca.sh desafios/v6 candidata-g10.json candidata-g20.json candidata-g30.json
```

`--seed N` fixa a semente (para reproduzir um desafio antigo) e `--sem-confirmacao` desliga a regra 5; os dois ficam gravados no resultado e só devem ser usados com registro do motivo.
