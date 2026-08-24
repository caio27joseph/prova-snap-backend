# Trabalho paralelo com git worktrees

Convenções para desenvolver mais de um bloco (branch) ao mesmo tempo na mesma
máquina, sem clones duplicados. Complementa a estratégia de branches em
[`COMMIT_STRATEGY.md`](COMMIT_STRATEGY.md).

## Layout

Worktrees vivem **fora** do repositório, em um diretório irmão:

```
~/Documents/
├── prova-snap-backend/            # checkout principal (main) — dono do Docker
└── prova-snap-backend.wt/
    ├── parte1-auth-design/        # um worktree por branch em andamento
    └── parte2-models-migrations/
```

Fora do repo porque ferramentas que varrem a árvore (pytest, ruff, git) nunca
devem enxergar um checkout aninhado.

## Comandos (`scripts/wt.sh`)

| Comando | Faz |
|---|---|
| `scripts/wt.sh new <branch>` | Cria worktree + branch a partir de `main`, **copia o `.env` local** e roda `uv sync` |
| `scripts/wt.sh list` | Lista worktrees ativos |
| `scripts/wt.sh rm <branch>` | Remove com segurança: recusa se houver mudança não commitada ou branch não mergeada; a branch é preservada |

## As três regras que evitam dor

1. **Um único Postgres para todos os worktrees.** `docker compose` roda
   somente no checkout principal. Rodar `up` dentro de um worktree criaria um
   segundo stack (o Compose nomeia o projeto pelo diretório) e colidiria na
   porta do host. O `.env` copiado já aponta cada worktree para a instância
   compartilhada.
2. **Uma porta de uvicorn por worktree.** `--port 8001`, `8002`… — apps
   paralelos não disputam a 8000.
3. **Suítes de teste em série, por enquanto.** Todos os worktrees compartilham
   o banco `prova_test`; duas suítes simultâneas corromperiam as fixtures uma
   da outra. Decisão registrada: o `conftest.py` da Parte 2 vai honrar
   `TEST_DATABASE_URL`, permitindo um banco de teste por worktree
   (`prova_test_parte2_auth`, …) e destravando o paralelismo completo.

## Ciclo de vida de um bloco

```bash
scripts/wt.sh new parte2-auth          # abrir
cd ../prova-snap-backend.wt/parte2-auth
# ... desenvolver, commits pequenos (com aprovação — CLAUDE.md) ...
uv run pytest                          # suíte verde é pré-condição de merge
cd ~/Documents/prova-snap-backend
git merge --no-ff parte2-auth -m "merge: ..."
scripts/wt.sh rm parte2-auth           # fechar; branch fica para a narrativa
```

As skills `worktree-new` e `worktree-finish` guiam agentes de IA por esse
mesmo ciclo.
