# Guia de Desenvolvimento — requisitos e regras

O contrato de trabalho deste repositório: o que a máquina precisa ter, o que o
desenvolvedor (humano ou IA) **deve** fazer em cada etapa, e o que fica
deliberadamente de fora. Os documentos de estratégia detalham cada área:
[commits/branches](COMMIT_STRATEGY.md) · [testes](TEST_STRATEGY.md) ·
[worktrees](WORKTREES.md) · [requisitos da prova](REQUIREMENTS.md).

## Requisitos da máquina

| Ferramenta | Para quê | Verificação |
|---|---|---|
| Docker + Compose | PostgreSQL de dev e teste | `docker compose version` |
| [uv](https://docs.astral.sh/uv/) | Python 3.12+, dependências, venv | `uv --version` |
| git ≥ 2.5 | Fluxo de worktrees | `git --version` |

Setup do zero: `make up && uv sync` — depois `make dev` e abrir
<http://localhost:8000/health>. Porta 5432 ocupada? Ver seção no
[README](../README.md).

## Atalhos padronizados (`Makefile`)

`make up` · `make dev` · `make test` · `make lint` · `make fmt` ·
`make check` (= lint + test, o gate de merge).

## O desenvolvedor DEVE

1. **Trabalhar em branch por bloco**, criada via `scripts/wt.sh new <branch>`
   (nomes na tabela do [COMMIT_STRATEGY](COMMIT_STRATEGY.md)). `main` recebe
   apenas merges `--no-ff` de blocos com suíte verde; ajustes de uma linha
   podem ir direto.
2. **Antes de cada commit:** `make fmt` e `make lint` limpos; Conventional
   Commit pequeno, em inglês, corpo explicando o porquê. Agentes de IA:
   propor o commit e **aguardar aprovação explícita** (regra do CLAUDE.md).
3. **Antes de cada merge:** `make check` verde dentro do worktree; merge
   feito do checkout principal; branch preservada.
4. **Registrar decisões em tempo real:** decisão de engenharia relevante →
   entrada no `AI_ENGINEERING_LOG.md` **no mesmo commit** da mudança.
   Sugestão de IA rejeitada ou errada → seção 3 do log, na hora.
5. **Nunca commitar segredos.** `.env` é local e gitignorado;
   `.env.example` documenta as variáveis; defaults de dev vivem em
   `app/config.py`.
6. **Gerenciar dependências só via `uv add`/`uv remove`** — `pyproject.toml`
   e `uv.lock` mudam juntos, no mesmo commit, com o porquê da lib no corpo.
7. **Migrations sempre aditivas via Alembic** (`alembic revision`); migration
   já aplicada nunca é editada — cria-se outra.
8. **Comentar apenas decisões não-óbvias** no código (exigência da prova);
   identificadores e mensagens em inglês, docs entregáveis em pt-BR.
9. **Testar caminhos de erro junto com a feature** — a matriz do
   [TEST_STRATEGY](TEST_STRATEGY.md) é o alvo; teste novo entra no mesmo
   bloco da funcionalidade que ele prova.
10. **Manter os docs sincronizados:** mudança que altera como rodar/testar →
    atualiza README/skills no mesmo bloco.

## Deliberadamente fora (com justificativa)

- **pre-commit hooks** — o gate é manual (`make check`) + revisão; instalar
  hooks adicionaria fricção ao avaliador sem ganho numa equipe de um.
- **CI real** — descrita na Parte 4, como o enunciado pede.
- **mypy/pyright no gate** — tipagem já vem de SQLAlchemy 2 `Mapped[]` +
  Pydantic v2 em runtime; um type-checker entraria como melhoria, não como
  requisito da prova.
