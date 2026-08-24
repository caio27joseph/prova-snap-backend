# Estratégia de Escalabilidade

Avaliação honesta de como a solução escala, o que foi preparado desde já e o
que fica deliberadamente para depois (com o caminho aberto). Este documento
fundamenta parte das escolhas da Parte 4.

## Por que um serviço único — e não microserviços

A pergunta é legítima: a plataforma tem 3 aplicações, por que não 3 serviços?
Decisão explícita: **monólito modular, um único serviço FastAPI.**

1. **O enunciado fecha a porta.** A Parte 2 pede "um endpoint de busca
   unificada **compartilhado** pelas 3 aplicações" — um `/api/v1/search`, com
   comportamento variando por permissão. As "3 aplicações" (Analytics,
   Investigator, Case Manager) são os *produtos* da plataforma — clients do
   realm no Keycloak — que **consomem** este backend; não são três serviços a
   construir. Três buscas separadas seria o oposto do requisito.
2. **Contexto on-premises.** A plataforma roda na infraestrutura do cliente
   (órgãos de controle). Cada serviço adicional é uma peça que *o cliente*
   opera: deploy, upgrade, rede entre serviços, monitoramento. Microserviços
   multiplicam custo operacional exatamente onde ele é mais caro — em dezenas
   de instalações que não controlamos.
3. **Problemas distribuídos sem ganho.** A busca agregada e a trilha de
   auditoria em tabela única são triviais num serviço só; com serviços
   separados viram fan-out por rede e consistência distribuída da trilha —
   dor real, benefício nenhum no volume atual.
4. **Pragmatismo avaliado.** Solução simples e efetiva é critério explícito
   da rubrica; microserviços aqui seria abstração especulativa.

**A parte importante: o monólito é modular com as costuras prontas.** Se um
dia a extração se justificar, o custo é baixo por desenho, não por sorte:

- O *strategy per app* isola cada regra de busca atrás de uma interface — um
  strategy é um candidato natural a serviço.
- A resposta agrupada por app já é scatter-gather — o agregador não muda de
  contrato se uma fonte virar chamada de rede.
- O caminho de shard funcional (abaixo) — um banco por domínio sem mudar o
  contrato do endpoint — é literalmente o primeiro passo de uma extração.
- Comunicação entre serviços (Investigator → Analytics) é tratada na Parte 1,
  Cenário 2, via service accounts — em arquitetura escrita, onde o enunciado
  a colocou, não em código.

Critério objetivo para revisitar: extração se justifica quando um domínio
precisar de **ciclo de deploy ou escala independente** (ex.: Investigator com
carga 10× maior exigindo réplicas próprias) — não antes.

## Diagnóstico: onde a solução está hoje

| Dimensão | Estado atual | Veredito |
|---|---|---|
| App servers | API stateless (JWT, sem sessão em memória) | Escala horizontal trivial (réplicas atrás de load balancer) |
| Leitura | Busca é read-only em Postgres single-node | Read replicas resolvem antes de qualquer shard |
| Paginação | Sem cursor; LIMIT interno fixo como guarda | Preparada, não implementada (ver abaixo) |
| Busca textual | `ILIKE '%termo%'` → seq scan | Gargalo conhecido; mitigação (pg_trgm/FTS) é melhoria da Parte 4 |
| Escrita | Audit log síncrono no fluxo da busca; tabela de maior crescimento | Em escala: particionar por tempo e/ou enfileirar async |
| Sharding | Nenhum | Caminho natural existe pelo design (ver abaixo) |

## Decisão estruturante: UUIDv7 como chave primária

O tipo de ID é a decisão barata-agora/cara-depois: trocar a PK com dados vivos
é uma das migrações mais caras que existem. Adotamos **UUIDv7** (gerado na
aplicação, pacote `uuid-utils` — Python 3.12 não tem `uuid7` nativo) porque
resolve os dois requisitos de escala com uma decisão só:

1. **Cursor keyset:** UUIDv7 embute timestamp nos bits mais significativos —
   é ordenável por tempo. `WHERE id > :cursor ORDER BY id LIMIT :n` é um
   cursor estável sob inserções concorrentes (offset/`OFFSET` não é).
2. **Shard-ready:** geração é local e sem coordenação — qualquer nó/shard
   gera IDs sem colisão, ao contrário de `BIGSERIAL` (sequência central).

Alternativas rejeitadas: `BIGSERIAL` + cursor composto `(created_at, id)`
(mais compacto, mas não sobrevive a shard); BIGINT estilo Snowflake
(shard-ready, mas exige infraestrutura de gerador — over-engineering aqui).
Custo assumido do UUIDv7: 16 bytes vs 8, e índices um pouco maiores — sem a
fragmentação de B-tree do UUIDv4, que é aleatório.

### Adendo: geração na aplicação com múltiplas instâncias — colisões são um problema?

**Não — e este é justamente o caso de uso nativo do UUIDv7.** A pergunta é
legítima (IDs gerados fora do banco, por N instâncias independentes, soam
arriscados), então a análise explícita:

**Por que colisões não são um problema na prática.** O UUIDv7 (RFC 9562) tem
48 bits de timestamp em milissegundos + 74 bits aleatórios. Colidir exige dois
IDs no **mesmo milissegundo** com os **mesmos 74 bits sorteados**. Pelo
paradoxo do aniversário, com `k` IDs gerados no mesmo ms em todo o sistema, a
probabilidade de colisão é ≈ k²/2⁷⁵. Mesmo num cenário absurdo para esta
plataforma — 1 milhão de inserções por milissegundo somando todas as
instâncias — isso dá ≈ 2,6×10⁻¹¹ por ms. É o mesmo modelo de unicidade
**probabilística** do UUIDv4 (consagrado em produção há décadas), trocando
parte da aleatoriedade por ordenação temporal. É exatamente essa propriedade
que dispensa coordenação: nenhuma faixa a reservar, nenhum node-id a
configurar (Snowflake), nenhuma sequência central (`BIGSERIAL`).

**Rede de segurança determinística.** Se o evento de 10⁻¹¹ acontecer, a
PRIMARY KEY do Postgres o transforma em `UniqueViolation` explícita na
inserção — nunca corrupção silenciosa. Deliberadamente **não** há retry no
código: uma mitigação para um evento dessa ordem custaria mais em manutenção
do que protege, e a constraint já garante visibilidade do erro.

**Duas nuances de multi-instância (nenhuma é colisão, nenhuma quebra o cursor):**

1. *Ordem intra-milissegundo não é cronológica global* — entre instâncias, IDs
   do mesmo ms se ordenam pelos bits aleatórios. Irrelevante para paginação
   keyset, que exige apenas uma **ordem total estável e determinística** — e a
   ordenação por bytes do UUID dá isso: nenhum item é pulado ou repetido entre
   páginas.
2. *Clock skew entre nós* — com NTP, relógios divergem em poucos ms, então a
   ordem temporal entre instâncias não é perfeita. Afeta a pureza cronológica,
   não a unicidade nem a estabilidade do cursor.

Dentro de um mesmo processo, a lib `uuid-utils` ainda garante monotonicidade
em rajadas (contador nos bits sub-ms). Conclusão: adicionar instâncias não
enfraquece o esquema de IDs — fortalece o argumento de tê-lo escolhido.

## Paginação por cursor: preparada, não implementada

O enunciado lista paginação explicitamente como melhoria futura (Parte 4), e o
rubric premia não construir feature não pedida. O que fica pronto desde já:

- **IDs ordenáveis** (UUIDv7) — o cursor é o próprio `id` do último item.
- **Envelope de resposta por app** que já comporta o campo futuro:
  `"investigator": {"items": [...], "next_cursor": null}`.
- **LIMIT interno fixo** (guarda de recurso): nenhuma busca devolve a tabela
  inteira, documentado no contrato.
- **Cursor por seção, não global:** como cada app retorna um shape próprio,
  cada seção pagina independentemente (um `next_cursor` para investigator,
  outro para cases). **Analytics não pagina** — retorna agregados, não linhas.

Custo residual de implementar depois: só o endpoint (aceitar `cursor` no body
POST — outro motivo da escolha de POST — e devolver `next_cursor`). Zero
migração de schema.

## Caminho de sharding (na ordem em que faria sentido)

Escala se compra na ordem do gargalo, não de uma vez:

1. **Bound de recursos** (feito): LIMIT fixo + índices B-tree nos filtros.
2. **Busca textual**: `pg_trgm`/full-text search (Parte 4) — remove o seq scan.
3. **Read replicas**: busca é read-only; só o audit log escreve no primário.
4. **Particionamento do audit log por tempo** (`pg_partman`): maior tabela em
   crescimento, acesso sempre recente — particionar antes de shardar.
5. **Shard funcional (primeiro corte real)**: o design já corta sozinho — o
   *strategy per app* + resposta agrupada por app significam que
   `analytics_reports`, `investigator_entities` e `case_manager_cases` podem
   ir cada um para um banco próprio **sem mudar o contrato do endpoint**: o
   serviço já faz scatter-gather por app e agrega no final.
6. **Shard dentro de um domínio** (último recurso, via Citus ou na aplicação):
   chaves naturais já existentes — `assigned_to` no Case Manager (busca é
   sempre "meus casos" → shard local à consulta), tempo no audit log. UUIDv7
   garante unicidade entre shards sem coordenação.

## O que deliberadamente NÃO fazemos agora

Cache distribuído, filas para o audit, Citus, réplicas — tudo descrito acima é
estratégia, não implementação. O escopo da prova pede busca funcional simples;
construir infraestrutura de escala especulativa violaria o critério de
pragmatismo. A aposta registrada: as duas decisões irreversíveis-na-prática
(tipo da PK e formato do contrato de resposta) foram tomadas olhando para a
escala; todo o resto é reversível e fica para quando o gargalo aparecer.
