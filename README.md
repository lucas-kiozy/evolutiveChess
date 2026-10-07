# evolutiveChess

Um jogo de xadrez em Python com uma inteligência evolutiva chamada **Luna**. A Luna aprende jogando contra outras Lunas, em várias partidas em paralelo, e cada geração seleciona os melhores descendentes por algoritmo genético. Quando a Luna atingir rating equivalente a ~1600, ela passa a jogar no [Lichess](https://lichess.org/), uma partida por vez, e continua se aperfeiçoando.

> **Status atual:** fase de planejamento. Nenhum código foi escrito ainda.
> O relatório completo do que já foi feito e do que falta está em [docs/STATUS.md](docs/STATUS.md).

## Etapas do projeto

| # | Etapa | Status |
|---|-------|--------|
| 1 | Jogo de xadrez funcional com todas as regras validadas | Não iniciada |
| 2 | Luna: IA evolutiva com algoritmo genético | Não iniciada |
| 3 | Self-play paralelo: Luna contra Luna, seleção dos melhores descendentes | Não iniciada |
| 4 | Medição de rating (meta: ~1600) | Não iniciada |
| 5 | Luna jogando no Lichess, partida a partida, e evoluindo | Não iniciada |

O detalhamento de cada etapa, com backlog e critérios de pronto, está em [docs/STATUS.md](docs/STATUS.md).

## Critério de aptidão da Luna

Definido pelo Lucas para escolher os melhores descendentes:

1. **Vitória com menos jogadas:** vence a Luna que precisou de menos lances para dar xeque-mate.
2. **Desempate:** se o critério acima empatar, vence a Luna que deu **menos xeques** durante a partida.

O tratamento de partidas empatadas (afogamento, repetição, regra dos 50 lances, material insuficiente) ainda está em aberto; veja "Decisões em aberto" no relatório.

## Organização do trabalho

O projeto é tocado por frentes de trabalho (agentes) com focos diferentes:

| Frente | Responsabilidade |
|--------|------------------|
| Motor de xadrez | Tabuleiro, geração de lances legais, validação de todas as regras, testes |
| Luna | Genoma, função de avaliação, busca, operadores genéticos, self-play paralelo |
| Rating e Lichess | Medição de rating contra adversários calibrados, integração com a API de bots do Lichess |
| Documentação | Este README e o relatório em `docs/`, atualizados a cada alteração concluída |

A definição do agente de documentação está em [.claude/agents/documentador.md](.claude/agents/documentador.md).

## Estrutura do repositório

```
.
├── README.md                 # visão geral (este arquivo)
├── docs/
│   ├── STATUS.md             # relatório: o que foi feito e backlog
│   └── REFERENCIAS.md        # base científica e técnica do projeto
└── .claude/agents/
    └── documentador.md       # agente que mantém a documentação
```

A estrutura do código (pacotes do motor, da Luna e da integração com o Lichess) será documentada aqui assim que as primeiras alterações forem incorporadas.

## Como executar

Ainda não há código executável. Esta seção será preenchida quando o motor de xadrez estiver disponível.

## Referências

A base científica das escolhas do projeto (algoritmos genéticos aplicados a xadrez, sistemas de rating) está em [docs/REFERENCIAS.md](docs/REFERENCIAS.md).
