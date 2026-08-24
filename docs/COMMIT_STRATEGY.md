# Estratégia de Commits e Branches

O histórico do repositório faz parte da avaliação: ele deve contar a história do
desenvolvimento em passos pequenos e justificados. Este documento define as regras
seguidas durante toda a prova e complementa as diretrizes de trabalho com IA em
[`CLAUDE.md`](../CLAUDE.md).

## Convenção de mensagens: Conventional Commits

Mensagens em **inglês** (convenção do projeto), no formato:

```
<tipo>(<escopo opcional>): <resumo no imperativo, minúsculo, sem ponto final>

<corpo opcional: explica o PORQUÊ quando a mudança não é óbvia>
```

### Tipos usados neste projeto

| Tipo | Uso |
|---|---|
| `feat` | Nova funcionalidade da API (auth, search, audit) |
| `fix` | Correção de comportamento errado |
| `test` | Adição ou ajuste de testes |
| `docs` | Documentação (README, docs/, respostas escritas) |
| `chore` | Infra do repo: tooling, docker-compose, dependências, config |
| `refactor` | Mudança de estrutura sem mudança de comportamento |

### Escopos

Escopos curtos e estáveis, alinhados à estrutura do projeto:
`auth`, `search`, `audit`, `models`, `migrations`, `parte1`, `parte3`, `parte4`, `ai-log`.

### Exemplos

```
docs: add requirements extracted from exam PDF
chore: scaffold FastAPI project with tooling and docker-compose
feat(auth): add JWT dependency with mocked Keycloak claims
feat(search): add analytics strategy with permission enforcement
test(search): return 403 when user lacks app permission
docs(parte1): justify single-realm SSO decision
```

### Regras de conteúdo

- **Um commit = um passo lógico.** Se a mensagem precisa de "and", provavelmente
  são dois commits.
- **Corpo explica o porquê**, nunca o quê (o diff já mostra o quê). Decisões
  não óbvias referenciam o doc onde foram justificadas
  (ex.: `See docs/TEST_STRATEGY.md`).
- Commits que registram uma decisão de engenharia relevante devem ter a decisão
  espelhada em `AI_ENGINEERING_LOG.md` **no mesmo commit** — o log é mantido em
  tempo real, não reconstruído.

## Estratégia de branches: uma branch por Parte

Trabalho solo, mas com branches de feature para que o histórico mostre blocos de
trabalho coesos e mergeados de forma deliberada.

### Fluxo

1. `main` sempre estável: em `main`, a suíte de testes passa.
2. Cada bloco de trabalho nasce em uma branch própria, a partir de `main`.
3. Merge para `main` com **`--no-ff`** (merge commit explícito), para que a
   estrutura de branches fique visível em `git log --graph`. A mensagem do merge
   resume o bloco entregue.
4. Branches não são apagadas antes da entrega — fazem parte da narrativa.

> **Por que `--no-ff`:** com fast-forward o merge desaparece do histórico e a
> branch vira indistinguível de commits diretos em `main`; o merge commit é o
> marcador de "bloco concluído" que o avaliador consegue enxergar.

### Branches planejadas

| Branch | Conteúdo |
|---|---|
| `setup` | Scaffold do projeto, tooling, docker-compose, estratégias (este doc) |
| `parte1-auth-design` | Resposta escrita da Parte 1 + `docs/JWT_STRUCTURE.md` |
| `parte2-models-migrations` | Models SQLAlchemy + migration Alembic + seed |
| `parte2-auth` | Dependency JWT + validação de permissões |
| `parte2-search` | Endpoint `/api/v1/search`, estratégias por app, agregação, audit |
| `parte2-error-paths` | Testes e tratamento de erro além do caminho feliz |
| `parte3-incident` | Resposta escrita da Parte 3 |
| `parte4-tradeoffs` | Resposta escrita da Parte 4 |

Ajustes pontuais pós-merge (typo, fix pequeno) podem ir direto em `main` — criar
branch para um commit de uma linha seria cerimônia sem valor.

## O que NÃO fazer

- Commits gigantes "wip" ou "final adjustments".
- Rebase/squash que apague a sequência real de trabalho — o histórico honesto
  (incluindo correções) é parte da avaliação AI-First.
- Mensagens em português (código e histórico ficam em inglês; documentação
  entregue ao cliente fica em pt-BR).
