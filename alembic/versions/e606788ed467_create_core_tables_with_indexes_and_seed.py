"""create core tables with indexes and seed

Single migration for Parte 2: the four tables, B-tree indexes on filter
columns only, and a deterministic pt-BR seed (10 rows per domain table).

Index policy (AI log, Decisão 4): B-tree only where the search strategies
actually filter. No trigram/full-text index on title/content/name — ILIKE
'%term%' cannot use a B-tree anyway, and pg_trgm/FTS is exactly the
"optimized search" the exam puts out of scope (listed as a Parte 4
improvement instead).

Seed determinism: every id and created_at is a hardcoded literal, so tests
can assert against known data and `alembic upgrade head` produces the same
database everywhere. The UUIDv7 ids were generated once at authoring time;
their embedded timestamp intentionally differs from created_at — the column,
not the id, is the time source (Decisão 7).

Revision ID: e606788ed467
Revises:
Create Date: 2026-08-24 07:09:28.289942

"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e606788ed467"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

U = uuid.UUID

# Mock Keycloak user UUIDs (app/auth/mock_users.py — `sub` claims). Literals,
# not imports: a migration must stay immutable even if the registry moves.
ANA = U("01a03323-fe61-72b0-9ac6-8524ead7cf87")
OUTRO = U("01a03323-fe61-72b0-9ac6-85486f005be6")
JOAO = U("01a03323-fe61-72b0-9ac6-84f42896edd4")


def _ts(year: int, month: int, day: int, hour: int = 12) -> datetime:
    return datetime(year, month, day, hour, tzinfo=UTC)


def upgrade() -> None:
    analytics_reports = op.create_table(
        "analytics_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    investigator_entities = op.create_table(
        "investigator_entities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        # No CHECK on type (deliberate): the search layer filters by the
        # allowed-type list; the table may hold other types (seed: 'veiculo').
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("data", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    case_manager_cases = op.create_table(
        "case_manager_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("assigned_to", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    op.create_table(
        "search_audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        # NULLable by design (Decisão 6): a denied search (403) has no searched
        # app and no result count — only origin, user, query and status.
        sa.Column("app", sa.String(), nullable=True),
        sa.Column("origin_app", sa.String(), nullable=False),
        sa.Column("query", sa.String(), nullable=False),
        sa.Column("results_count", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column(
            "timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("status IN ('ok', 'denied')", name="ck_search_audit_log_status"),
    )

    # Investigator strategy always filters WHERE type IN (<searchable types>).
    op.create_index("ix_investigator_entities_type", "investigator_entities", ["type"])
    # Case Manager's ownership rule makes every query filter on assigned_to.
    op.create_index("ix_case_manager_cases_assigned_to", "case_manager_cases", ["assigned_to"])
    # Status is the natural workload filter for case listings ('aberto', ...).
    op.create_index("ix_case_manager_cases_status", "case_manager_cases", ["status"])
    # Forensic question 1: "what did user X search, and when?" — one index scan.
    op.create_index(
        "ix_search_audit_log_user_id_timestamp", "search_audit_log", ["user_id", "timestamp"]
    )
    # Forensic question 2: "who accessed app Y's data this month?" (Decisão 6).
    op.create_index("ix_search_audit_log_app_timestamp", "search_audit_log", ["app", "timestamp"])

    # --- Seed -----------------------------------------------------------------
    # created_at spread over Jan–Jun/2026 (>= 3 distinct months) so the
    # Analytics by_month aggregation is testable against known buckets.
    # Two rows carry the literals "100%" / "1000" as fixtures for the future
    # escape_like test (searching "100%" must not match "1000").
    op.bulk_insert(
        analytics_reports,
        [
            {
                "id": U("01a0333c-adb7-7021-bf24-9ee453a23249"),
                "title": "Movimentações atípicas em contas de passagem — Janeiro/2026",
                "content": (
                    "Análise de 42 transferências fracionadas entre contas de passagem "
                    "ligadas ao Grupo Aurora, com indícios de estruturação (smurfing)."
                ),
                "created_at": _ts(2026, 1, 12, 9),
            },
            {
                "id": U("01a0333c-adb7-7021-bf24-9eff27fcbb6f"),
                "title": "Vínculos societários do Grupo Aurora",
                "content": (
                    "Mapeamento societário identificou três empresas com sócios em comum "
                    "e sede no mesmo endereço fiscal em Curitiba/PR."
                ),
                "created_at": _ts(2026, 1, 27, 15),
            },
            {
                "id": U("01a0333c-adb7-7021-bf24-9f08438f0b99"),
                "title": "Transferências internacionais — Fevereiro/2026",
                "content": (
                    "Remessas para jurisdições de sigilo somaram R$ 2,4 milhões no mês, "
                    "concentradas em dois beneficiários finais."
                ),
                "created_at": _ts(2026, 2, 5, 10),
            },
            {
                "id": U("01a0333c-adb7-7021-bf24-9f189a43da14"),
                "title": "Operações fracionadas em espécie",
                "content": (
                    "Depósitos em espécie logo abaixo do limite de reporte, repetidos em "
                    "sete agências distintas no intervalo de duas semanas."
                ),
                "created_at": _ts(2026, 2, 19, 11),
            },
            {
                "id": U("01a0333c-adb7-7021-bf24-9f2d9a86ebd3"),
                "title": "Consolidado trimestral de alertas COAF",
                "content": (
                    "Dos 118 alertas recebidos no trimestre, 100% dos casos priorizados "
                    "tinham vínculo com empresas de fachada do setor de fretes."
                ),
                "created_at": _ts(2026, 3, 3, 9),
            },
            {
                "id": U("01a0333c-adb7-7021-bf24-9f394623a161"),
                "title": "Fluxo financeiro — Operação Maré Alta",
                "content": (
                    "Reconstrução do fluxo entre a Maré Alta Transportes e fornecedores "
                    "de fachada; camada final pulverizada em contas de laranjas."
                ),
                "created_at": _ts(2026, 3, 21, 16),
            },
            {
                "id": U("01a0333c-adb7-7021-bf24-9f49030fd537"),
                "title": "Contas de passagem identificadas",
                "content": (
                    "Nove contas com permanência média de recursos inferior a 48 horas, "
                    "compatível com camada de ocultação."
                ),
                "created_at": _ts(2026, 4, 8, 14),
            },
            {
                "id": U("01a0333c-adb7-7021-bf24-9f59fc376c29"),
                "title": "Empresas de fachada — setor de fretes",
                "content": (
                    "Doze transportadoras sem frota própria emitiram notas de serviço; "
                    "faturamento médio declarado de R$ 1000,00 por viagem não condiz com "
                    "o mercado."
                ),
                "created_at": _ts(2026, 4, 23, 10),
            },
            {
                "id": U("01a0333c-adb7-7021-bf24-9f68d3e37e89"),
                "title": "Crescimento patrimonial incompatível",
                "content": (
                    "Evolução patrimonial de investigado supera em 14 vezes a renda "
                    "declarada no período 2023–2025."
                ),
                "created_at": _ts(2026, 5, 14, 9),
            },
            {
                "id": U("01a0333c-adb7-7021-bf24-9f7e96da76ee"),
                "title": "Síntese preliminar de tipologias de lavagem",
                "content": (
                    "Tipologias predominantes: estruturação em espécie, contas de "
                    "passagem e superfaturamento de serviços de transporte."
                ),
                "created_at": _ts(2026, 6, 2, 11),
            },
        ],
    )

    # 9 rows across the 4 searchable types + 1 'veiculo': proof row that the
    # type filter (not a DB constraint) is what keeps results searchable-only.
    op.bulk_insert(
        investigator_entities,
        [
            {
                "id": U("01a0333c-adb7-7021-bf24-9f8b36702501"),
                "type": "pessoa",
                "name": "Carlos Alberto Menezes",
                "data": {"cpf": "412.878.290-53", "nascimento": "1978-03-14", "uf": "PR"},
                "created_at": _ts(2026, 1, 15, 10),
            },
            {
                "id": U("01a0333c-adb7-7021-bf24-9f9011b06013"),
                "type": "pessoa",
                "name": "Fernanda Oliveira Duarte",
                "data": {"cpf": "529.982.247-25", "profissao": "contadora", "uf": "SP"},
                "created_at": _ts(2026, 1, 30, 14),
            },
            {
                "id": U("01a0333c-adb7-7021-bf24-9fa8ce84eef7"),
                "type": "pessoa",
                "name": "Roberto Nunes Sampaio",
                "data": {"cpf": "168.995.350-09", "apelido": "Beto do Frete", "uf": "SC"},
                "created_at": _ts(2026, 2, 11, 9),
            },
            {
                "id": U("01a0333c-adb7-7021-bf24-9fb1dc11a090"),
                "type": "empresa",
                "name": "Aurora Comércio de Alimentos LTDA",
                "data": {"cnpj": "12.345.678/0001-90", "situacao": "ativa", "uf": "PR"},
                "created_at": _ts(2026, 2, 25, 16),
            },
            {
                "id": U("01a0333c-adb7-7021-bf24-9fcade624fb1"),
                "type": "empresa",
                "name": "Maré Alta Transportes ME",
                "data": {"cnpj": "98.765.432/0001-10", "situacao": "baixada", "frota": 0},
                "created_at": _ts(2026, 3, 9, 10),
            },
            {
                "id": U("01a0333c-adb7-7021-bf24-9fd13e5b3dc8"),
                "type": "transacao",
                "name": "TED 2026-0114 Aurora para Maré Alta",
                "data": {"valor": 250000.00, "moeda": "BRL", "data": "2026-01-14"},
                "created_at": _ts(2026, 3, 18, 11),
            },
            {
                "id": U("01a0333c-adb7-7021-bf24-9fe28a522531"),
                "type": "transacao",
                "name": "PIX 2026-0302 origem não identificada",
                "data": {"valor": 9800.50, "moeda": "BRL", "chave": "aleatoria"},
                "created_at": _ts(2026, 4, 2, 15),
            },
            {
                "id": U("01a0333c-adb7-7021-bf24-9ff492c86a8c"),
                "type": "documento",
                "name": "Contrato de prestação de serviços nº 44/2026",
                "data": {"paginas": 12, "hash_sha256": "9f2c1a", "origem": "busca e apreensão"},
                "created_at": _ts(2026, 4, 20, 9),
            },
            {
                "id": U("01a0333c-adb7-7021-bf24-a009b4218a99"),
                "type": "documento",
                "name": "Extrato bancário conta 44821-7",
                "data": {"paginas": 31, "banco": "341", "periodo": "2025-07 a 2025-12"},
                "created_at": _ts(2026, 5, 6, 13),
            },
            {
                "id": U("01a0333c-adb7-7021-bf24-a0193e797273"),
                "type": "veiculo",
                "name": "Caminhão Volvo FH 540 placa BRA2E19",
                "data": {"placa": "BRA2E19", "renavam": "00982123456", "cor": "branca"},
                "created_at": _ts(2026, 5, 22, 10),
            },
        ],
    )

    # Assignments: 4 cases for ANA, 3 for OUTRO, 3 for JOAO — enough to prove
    # the ownership filter (ANA never sees OUTRO's cases) with varied statuses.
    op.bulk_insert(
        case_manager_cases,
        [
            {
                "id": U("01a0333c-adb7-7021-bf24-a0297f94c871"),
                "title": "Fraude em licitação municipal de merenda",
                "assigned_to": ANA,
                "status": "aberto",
                "created_at": _ts(2026, 1, 20, 9),
            },
            {
                "id": U("01a0333c-adb7-7021-bf24-a031a7a51a12"),
                "title": "Caso 100% digital — fraude em leilão eletrônico",
                "assigned_to": ANA,
                "status": "em_andamento",
                "created_at": _ts(2026, 2, 14, 11),
            },
            {
                "id": U("01a0333c-adb7-7021-bf24-a040245b95d4"),
                "title": "Lavagem de dinheiro em rede de postos",
                "assigned_to": ANA,
                "status": "em_andamento",
                "created_at": _ts(2026, 3, 30, 15),
            },
            {
                "id": U("01a0333c-adb7-7021-bf24-a051e4dea392"),
                "title": "Ocultação de patrimônio em nome de terceiros",
                "assigned_to": ANA,
                "status": "fechado",
                "created_at": _ts(2026, 4, 11, 10),
            },
            {
                "id": U("01a0333c-adb7-7021-bf24-a06b25309cf8"),
                "title": "Desvio de recursos em obra pública",
                "assigned_to": OUTRO,
                "status": "aberto",
                "created_at": _ts(2026, 2, 3, 9),
            },
            {
                "id": U("01a0333c-adb7-7021-bf24-a0766b64d600"),
                "title": "Pirâmide financeira com criptoativos",
                "assigned_to": OUTRO,
                "status": "em_andamento",
                "created_at": _ts(2026, 3, 12, 14),
            },
            {
                "id": U("01a0333c-adb7-7021-bf24-a081af804986"),
                "title": "Sonegação fiscal em rede varejista",
                "assigned_to": OUTRO,
                "status": "fechado",
                "created_at": _ts(2026, 5, 8, 16),
            },
            {
                "id": U("01a0333c-adb7-7021-bf24-a09f66248a70"),
                "title": "Contrabando de eletrônicos na fronteira sul",
                "assigned_to": JOAO,
                "status": "aberto",
                "created_at": _ts(2026, 1, 25, 10),
            },
            {
                "id": U("01a0333c-adb7-7021-bf24-a0a5ffeb5bce"),
                "title": "Estelionato contra idosos — golpe do consignado",
                "assigned_to": JOAO,
                "status": "em_andamento",
                "created_at": _ts(2026, 4, 28, 9),
            },
            {
                "id": U("01a0333c-adb7-7021-bf24-a0bd4b8afed6"),
                "title": "Adulteração de combustível em distribuidora",
                "assigned_to": JOAO,
                "status": "fechado",
                "created_at": _ts(2026, 6, 10, 11),
            },
        ],
    )


def downgrade() -> None:
    # Indexes and constraints drop with their tables.
    op.drop_table("search_audit_log")
    op.drop_table("case_manager_cases")
    op.drop_table("investigator_entities")
    op.drop_table("analytics_reports")
