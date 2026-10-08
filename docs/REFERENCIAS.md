# Referências

Base científica e técnica das escolhas do projeto. Artigos revisados por pares aparecem primeiro em cada seção; fontes técnicas (documentação, wikis) vêm marcadas como tal.

## Algoritmos genéticos aplicados ao xadrez

- **Fogel, D. B., Hays, T. J., Hahn, S. L., & Quon, J. (2004).** A self-learning evolutionary chess program. *Proceedings of the IEEE*, 92(12), 1947–1954.
  Evoluiu os pesos de avaliação de um programa de xadrez apenas por partidas entre os próprios indivíduos da população, sem conhecimento de especialistas além das regras e de valores iniciais de material. É o precedente mais próximo da proposta da Luna (self-play + seleção). A aptidão usada foi por resultado de partida (vitória, empate, derrota).

- **David, O. E., van den Herik, H. J., Koppel, M., & Netanyahu, N. S. (2014).** Genetic algorithms for evolving computer chess programs. *IEEE Transactions on Evolutionary Computation*, 18(5), 779–789.
  Usa algoritmo genético para ajustar os parâmetros da função de avaliação e da busca de um motor de xadrez, chegando a força de nível de grande mestre. Mostra que o genoma natural para esse problema é o vetor de pesos da avaliação.

- **Holland, J. H. (1975).** *Adaptation in Natural and Artificial Systems*. University of Michigan Press.
  Obra que fundamenta os algoritmos genéticos (seleção, cruzamento, mutação).

- **Jin, Y., & Branke, J. (2005).** Evolutionary optimization in uncertain environments: a survey. *IEEE Transactions on Evolutionary Computation*, 9(3), 303–317.
  Revisão sobre algoritmos evolutivos com avaliação de aptidão ruidosa. Mostra que, quando a aptidão vem de poucas amostras, a seleção fica próxima do acaso, e que avaliar cada indivíduo em mais amostras (ou usar uma população maior) reduz o efeito. É o caso do primeiro treino da Luna, com 4 partidas por Luna em cada geração.

- **Rosin, C. D., & Belew, R. K. (1997).** New methods for competitive coevolution. *Evolutionary Computation*, 5(1), 1–29.
  Propõe o "hall da fama": cada indivíduo enfrenta também campeões de gerações passadas, o que evita que a população esqueça estratégias já vencidas e ande em círculos. Base das partidas da Luna contra campeãs passadas.

- **Pollack, J. B., & Blair, A. D. (1998).** Co-evolution in the successful learning of backgammon strategy. *Machine Learning*, 32(3), 225–240.
  Mostra que, em self-play, o campeão só deve ser trocado quando o desafiante o vence de forma consistente. Base da catraca de promoção da Luna.

- **Maron, O., & Moore, A. W. (1997).** The racing algorithm: model selection for lazy learners. *Artificial Intelligence Review*, 11(1–5), 193–225.
  Gasta avaliações extras só nos candidatos que ainda não se separaram estatisticamente. Base das partidas extras na fronteira da elite.

## Busca

- **Knuth, D. E., & Moore, R. W. (1975).** An analysis of alpha-beta pruning. *Artificial Intelligence*, 6(4), 293–326.
  Base da busca minimax com poda alfa-beta prevista para a Luna.

## Estatística das comparações

- **Wald, A. (1945).** Sequential tests of statistical hypotheses. *Annals of Mathematical Statistics*, 16(2), 117–186.
  Teste sequencial da razão de probabilidades (SPRT): para o match assim que há evidência suficiente. Usado na catraca de promoção (H0 0 Elo, H1 +30 Elo).

- **Glasserman, P., & Yao, D. D. (1992).** Some guidelines and guarantees for common random numbers. *Management Science*, 38(6), 884–908.
  Comparar alternativas sob as mesmas condições aleatórias reduz a variância da diferença. Base das partidas pareadas, com as mesmas aberturas para as duas cores.

- **Bradley, R. A., & Terry, M. E. (1952).** Rank analysis of incomplete block designs: I. The method of paired comparisons. *Biometrika*, 39(3/4), 324–345.
  Modelo de comparações pareadas que estima a força de cada jogador a partir dos confrontos. Usado para ordenar as Lunas de uma geração.

- **Hunter, D. R. (2004).** MM algorithms for generalized Bradley–Terry models. *Annals of Statistics*, 32(1), 384–406.
  Algoritmo de ajuste do modelo de Bradley–Terry, incluindo empates.

- **Efron, B., & Morris, C. (1975).** Data analysis using Stein's estimator and its generalizations. *Journal of the American Statistical Association*, 70(350), 311–319.
  Encolher estimativas ruidosas para a média melhora o erro total. Aplicado à força estimada de Lunas com poucas partidas.

## Rating

- **Elo, A. E. (1978).** *The Rating of Chessplayers, Past and Present*. Arco.
  Sistema Elo, referência para "rating equivalente a 1600".

- **Glickman, M. E. (1999).** Parameter estimation in large dynamic paired comparison experiments. *Journal of the Royal Statistical Society: Series C (Applied Statistics)*, 48(3), 377–394.
  Sistema Glicko, que inclui o desvio do rating (incerteza). O Lichess usa a variante Glicko-2, descrita por Glickman em nota técnica (não revisada por pares): <http://www.glicko.net/glicko/glicko2.pdf>.

## Fontes técnicas (não revisadas por pares)

- **Chess Programming Wiki — Perft Results:** <https://www.chessprogramming.org/Perft_Results>. Contagens de referência de nós por profundidade, usadas para validar o gerador de lances.
- **python-chess:** <https://python-chess.readthedocs.io/>. Biblioteca Python de regras de xadrez, útil como referência de validação.
- **Lichess Bot API:** <https://lichess.org/api#tag/Bot>. Documentação para contas BOT jogarem por API.
