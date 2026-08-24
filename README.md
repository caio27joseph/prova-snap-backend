# Busca Multi-Aplicação — Prova Técnica Backend (Snap Forensics)

API de **busca unificada** para uma plataforma de inteligência investigativa
composta por três aplicações — **Analytics** (relatórios), **Investigator**
(entidades e vínculos) e **Case Manager** (casos investigativos).

Em uma frase: o usuário faz **uma única busca** e recebe, na mesma resposta,
apenas os dados que **as suas permissões** autorizam ver em cada aplicação —
e toda busca fica registrada em uma **trilha de auditoria**.

## O que você precisa ter instalado

- **Docker** (com Docker Compose) — para o banco de dados PostgreSQL.
- **[uv](https://docs.astral.sh/uv/)** — gerenciador do projeto Python
  (cuida sozinho de instalar um Python compatível — 3.12 ou superior — e as dependências).

## Como rodar

Três comandos, nesta ordem:

```bash
docker compose up -d                       # 1. sobe o banco de dados
uv sync                                    # 2. instala as dependências
uv run uvicorn app.main:app --reload       # 3. inicia a API
```

Pronto. Para conferir se está tudo funcionando, abra
<http://localhost:8000/health> — a resposta esperada é
`{"status": "ok", "database": "up"}`.

A documentação interativa da API (onde dá para testar cada rota pelo
navegador) fica em <http://localhost:8000/docs>.

### Como rodar os testes

```bash
docker compose up -d    # se ainda não estiver de pé
uv run pytest
```

Os testes usam um banco separado (`prova_test`), criado automaticamente —
eles nunca tocam os dados de desenvolvimento.

### Porta 5432 ocupada?

Se a sua máquina já usa a porta padrão do PostgreSQL, crie um arquivo `.env`
na raiz com:

```
POSTGRES_PORT=5433
DATABASE_URL=postgresql+psycopg://prova:prova@localhost:5433/prova
```

## Como o projeto está organizado

| Pasta / arquivo | O que é |
|---|---|
| `app/` | O código da API (autenticação, busca, modelos de dados) |
| `alembic/` | Migrações do banco (criação das tabelas + dados de exemplo) |
| `tests/` | Testes automatizados |
| `docs/` | Documentação técnica e respostas escritas da prova |
| `AI_ENGINEERING_LOG.md` | Registro do uso de IA durante o desenvolvimento (Parte 5) |
| `docker-compose.yml` | Banco PostgreSQL para desenvolvimento e testes |

### Documentação para aprofundar

- [Parte 1 — Arquitetura de autenticação SSO](docs/PARTE1_AUTH.md)
- [Estrutura do JWT esperado](docs/JWT_STRUCTURE.md)
- [Estratégia de escalabilidade](docs/ESCALABILIDADE.md)
- [Estratégia de testes](docs/TEST_STRATEGY.md) · [Estratégia de commits](docs/COMMIT_STRATEGY.md)
- [Requisitos extraídos do enunciado](docs/REQUIREMENTS.md)

## Qualidade

A suíte automatizada tem **88 testes** — incluindo os 5 casos exigidos pela
prova e os caminhos de erro (token inválido/expirado, falta de permissão,
consulta inválida, banco indisponível, falha de auditoria) — e roda contra um
PostgreSQL real, aplicando as migrações de verdade. `make check` executa tudo.
A cada push, uma esteira automática no GitHub (CI) repete essa mesma
verificação — o projeto só avança se todos os testes continuarem passando.

### Monitoramento (opcional)

A API também expõe medições de saúde em tempo real — quanto tempo cada busca
demora, quantas requisições chegam e se alguma gravação da trilha de auditoria
falhou. Para visualizar isso em painéis gráficos, suba o modo de monitoramento
(a API precisa estar rodando com `--host 0.0.0.0`):

```bash
uv run uvicorn app.main:app --host 0.0.0.0   # a API, visível para os painéis
docker compose --profile observability up -d  # sobe Prometheus + Grafana
```

Depois abra <http://localhost:3000> (usuário `admin`, senha `admin`): o painel
"Search API — Observability" já aparece pronto, sem nenhuma configuração
manual. Esse modo é totalmente opcional — o `docker compose up -d` normal
continua subindo só o banco. Se as portas 3000 ou 9090 estiverem ocupadas na
sua máquina, defina `GRAFANA_PORT` e/ou `PROMETHEUS_PORT` no `.env`.
