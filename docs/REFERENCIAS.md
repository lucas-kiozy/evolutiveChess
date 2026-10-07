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

## Busca

- **Knuth, D. E., & Moore, R. W. (1975).** An analysis of alpha-beta pruning. *Artificial Intelligence*, 6(4), 293–326.
  Base da busca minimax com poda alfa-beta prevista para a Luna.

## Rating

- **Elo, A. E. (1978).** *The Rating of Chessplayers, Past and Present*. Arco.
  Sistema Elo, referência para "rating equivalente a 1600".

- **Glickman, M. E. (1999).** Parameter estimation in large dynamic paired comparison experiments. *Journal of the Royal Statistical Society: Series C (Applied Statistics)*, 48(3), 377–394.
  Sistema Glicko, que inclui o desvio do rating (incerteza). O Lichess usa a variante Glicko-2, descrita por Glickman em nota técnica (não revisada por pares): <http://www.glicko.net/glicko/glicko2.pdf>.

## Fontes técnicas (não revisadas por pares)

- **Chess Programming Wiki — Perft Results:** <https://www.chessprogramming.org/Perft_Results>. Contagens de referência de nós por profundidade, usadas para validar o gerador de lances.
- **python-chess:** <https://python-chess.readthedocs.io/>. Biblioteca Python de regras de xadrez, útil como referência de validação.
- **Lichess Bot API:** <https://lichess.org/api#tag/Bot>. Documentação para contas BOT jogarem por API.
