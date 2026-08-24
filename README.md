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
  (instala o Python 3.12+ e as dependências sozinho).

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

## Estado atual do desenvolvimento

> Seção temporária — removida na entrega final.

- [x] Infraestrutura: banco via Docker, projeto Python, endpoint `/health`
- [x] Decisões de arquitetura documentadas (11 decisões no log de IA)
- [ ] Parte 1 — resposta escrita (1.1 pronta; 1.2 e 1.3 pendentes)
- [ ] Parte 2 — modelos, migração com seed, autenticação JWT, endpoint de busca, testes
- [ ] Partes 3 e 4 — respostas escritas
