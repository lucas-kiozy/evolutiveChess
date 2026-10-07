# Plano: base do projeto e integração Luna + motor próprio

**Origem:** backlog em `docs/STATUS.md` (main, 2026-10-07), Etapa 0 e a ligação entre as Etapas 1 e 2.
**Linguagem:** Python (decisão do Lucas).
**Executado com:** subagent-driven-development (um implementador por tarefa, revisão após cada uma).

## Contexto

O repositório já tem quatro frentes trabalhando em paralelo. Este plano cobre só o que nenhuma delas assumiu:

| Frente | Onde | Estado em 2026-10-07 |
|---|---|---|
| Motor de xadrez | `chess_engine/` (PR #2) | pronto para revisão |
| Luna | `luna/` (PR #1) | rascunho; joga sobre python-chess por um adaptador provisório |
| Rating e Lichess | `lichess_bot/` (thread própria) | em andamento |
| Documentação | `README.md`, `docs/` | dona exclusiva desses arquivos |

Itens do backlog cobertos aqui (Etapa 0): estrutura de pacote Python, ferramentas de qualidade (pytest, lint), integração contínua. Mais a lacuna entre Etapa 1 e Etapa 2: a Luna ainda não usa o motor do projeto (`luna/adapters/__init__.py` deixa o gancho pronto para um adaptador `chess_engine`).

## Restrições globais

1. Não editar `README.md` nem nada em `docs/`. Ao concluir, avisar a frente de Documentação.
2. `chess_engine/`, `luna/` e `lichess_bot/` têm dono. Tarefas que tocam essas pastas só começam com confirmação do Lucas e depois que o PR da pasta estiver mergeado no main.
3. Os pacotes ficam na raiz do repositório (`chess_engine/`, `luna/`), não em `src/`. Não mover pastas.
4. Python mínimo: 3.10 (escolha do projeto: a versão mais antiga do CPython ainda suportada; é a base da matriz do CI).
5. Cada tarefa vai num PR contra `main`, com testes passando. As Tarefas 1 e 2 vão juntas num só PR, porque o CI da Tarefa 2 só é verificável com o `pyproject.toml` da Tarefa 1.
6. O motor `chess_engine` não tem dependências; isso continua assim. `chess` (python-chess) é dependência só da Luna e dos testes de comparação.

## Tarefas

### Task 1 (Tarefa 1): `pyproject.toml` na raiz

**Arquivos:** criar `pyproject.toml`, criar `.gitignore` na raiz.
**Toca pasta com dono?** Não.

Conteúdo exigido do `pyproject.toml`:

- `[build-system]`: `setuptools>=68`, `build-backend = "setuptools.build_meta"`.
- `[project]`: `name = "evolutivechess"`, `version = "0.1.0"`, `requires-python = ">=3.10"`, `description = "Xadrez em Python com a Luna, uma IA evolutiva por algoritmo genético"`, `dependencies = []`.
- `[project.optional-dependencies]`: `luna = ["chess>=1.10"]` e `dev = ["pytest>=8", "ruff>=0.6", "chess>=1.10"]`.
- `[tool.setuptools.packages.find]`: `include = ["chess_engine*", "luna*", "lichess_bot*"]`, `exclude = ["*.tests*"]`.
- `[tool.pytest.ini_options]`: `testpaths = ["chess_engine/tests", "luna/tests"]`, `addopts = "-q"`.
- `[tool.ruff]`: `line-length = 100`, `target-version = "py310"`. `[tool.ruff.lint]`: `select = ["E", "F", "I"]`.

`.gitignore` na raiz: `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.ruff_cache/`, `*.egg-info/`, `build/`, `dist/`, `.venv/`, `.superpowers/`.

**Teste de aceitação** (num venv limpo, a partir de um main que já tenha os PRs #1 e #2; se ainda não tiver, rodar sobre um checkout que junte os dois branches, sem commitá-los):

```
pip install -e ".[dev]"
python -m pytest                    # descobre e roda os testes do motor e da Luna
python -c "import chess_engine, luna"
ruff check .                        # roda; erros nas pastas com dono são relatados, não corrigidos
```

O relatório do implementador lista a saída do `ruff check .` por pasta.

### Task 2 (Tarefa 2): integração contínua no GitHub Actions

**Arquivos:** criar `.github/workflows/ci.yml`.
**Toca pasta com dono?** Não.
**Depende de:** Tarefa 1.

- Dispara em `pull_request` e em `push` para `main`.
- Job `testes`: matriz `python-version: ["3.10", "3.11", "3.12", "3.13"]`, `ubuntu-latest`, `actions/checkout@v4`, `actions/setup-python@v5` com `cache: pip`, `pip install -e ".[dev]"`, `python -m pytest`.
- Job `lint`: Python 3.12, `pip install ruff`, `ruff check .` e `ruff format --check .`, ambos com `continue-on-error: true` (o código das frentes ainda tem avisos; o lint vira bloqueante quando os donos limparem).
- Job `perft-profundo`: só em `push` para `main`, Python 3.12, `CHESS_SLOW=1 python -m pytest chess_engine/tests`.

**Teste de aceitação:** o workflow passa no `actionlint` (ou, sem ele, num YAML parse + revisão), e o PR desta tarefa mostra o job `testes` verde nas quatro versões.

### Task 3 (Tarefa 3): adaptador `chess_engine` para a Luna

**Arquivos:** criar `luna/adapters/chess_engine.py`, editar `luna/adapters/__init__.py` (registrar o backend), criar `luna/tests/test_adapter_chess_engine.py`.
**Toca pasta com dono?** Sim, `luna/`. Só começa com confirmação do Lucas e com os PRs #1 e #2 mergeados.

- Classe `ChessEngineGame` que implementa todo o protocolo `luna.game_interface.GameState` sobre `chess_engine.Board`, convertendo nas bordas:
  - lances: `move_to_uci` / `board.parse_uci` (a Luna fala UCI em string);
  - peças: inteiro com sinal do motor para letra maiúscula + booleano de cor;
  - `winner`: `WHITE`/`BLACK`/`None` do motor para `True`/`False`/`None`;
  - `termination`: mesmos nomes do motor (`checkmate`, `stalemate`, `insufficient_material`, `fifty_moves`, `threefold_repetition`, `seventyfive_moves`, `fivefold_repetition`).
- `captured_piece` devolve `"P"` em en passant.
- `mobility(white)`: casas atacadas pelas peças da cor que não estejam ocupadas por peças da mesma cor, mesma definição do adaptador python-chess.
- Registrar em `BACKENDS` com a chave `"chess-engine"`. **Não** mudar `DEFAULT_BACKEND` (decisão da frente da Luna).
- Testes:
  1. `isinstance(ChessEngineGame(), GameState)`.
  2. Conformidade: 200 partidas aleatórias com semente fixa (`random.Random(2026)`), até 200 meios-lances cada, jogadas lado a lado nos dois backends; a cada lance comparar `legal_moves()` (como conjunto), `is_check()`, `is_checkmate()`, `fen()`, `outcome()`, e para cada lance legal `is_capture`, `captured_piece`, `moving_piece`, `is_promotion`, `gives_check`. Pular o teste se `chess` não estiver instalado.
  3. Posições pontuais: en passant (`captured_piece == "P"`), promoção (`is_promotion`), mate do pastor (`outcome().termination == "checkmate"`, `winner is True`).
  4. Uma partida Luna × Luna curta (profundidade 1) com `backend="chess-engine"` termina sem erro.
- Atualizar o comentário em `luna/adapters/__init__.py` que sugere a chave `"chess_engine"`: a chave registrada é `"chess-engine"`.
- Remover do `.github/workflows/ci.yml` a tolerância ao código 5 do pytest (`|| [ $? -eq 5 ]`) e o comentário correspondente, já que os pacotes estarão na main.

### Task 4 (Tarefa 4): comparação de velocidade entre os backends

**Arquivos:** criar `tools/bench_backends.py`.
**Toca pasta com dono?** Não (só lê `luna/` e `chess_engine/`).
**Depende de:** Tarefa 3.

- Script de linha de comando: `python tools/bench_backends.py --partidas 20 --profundidade 2 --semente 2026`.
- Para cada backend registrado em `luna.adapters.BACKENDS`, roda as mesmas partidas Luna × Luna (mesmos genomas, mesma semente) e imprime uma tabela: backend, partidas, meios-lances totais, segundos, meios-lances por segundo, e se os resultados das partidas coincidem entre backends.
- Sem testes automatizados além de um smoke test em `tools/tests/test_bench.py` com `--partidas 1 --profundidade 1`, adicionado a `testpaths`.
- O resultado serve para a frente da Luna decidir o backend padrão; este plano não decide.

## Desvios na execução

A implementação da Tarefa 2 acrescentou o seguinte ao texto original:

- (a) o job `testes` trata o código de saída 5 do pytest ("nenhum teste coletado") como sucesso enquanto `chess_engine/` e `luna/` não estão na main;
- (b) os passos do `perft-profundo` só rodam se `chess_engine/tests` existir;
- (c) `fail-fast: false` na matriz;
- (d) `cache-dependency-path: pyproject.toml` no job `testes` e sem cache de pip nos outros jobs;
- (e) `permissions: contents: read` e `concurrency` no workflow;
- (f) ruff fixado em `>=0.6,<1` no job de lint.

## Fora deste plano

- Mudar o backend padrão da Luna, aptidão de empates e derrotas (decisões em aberto no `STATUS.md`).
- Rating e Lichess (thread própria).
- Atualizar `README.md`/`docs/STATUS.md` (frente de Documentação; avisar ao concluir cada tarefa).
