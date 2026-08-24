# Parte 1 — Arquitetura de Autenticação Multi-Aplicação

## 1.1 Decisão Fundamentada: Realm único com um client por aplicação (Opção A)

**Decisão: Opção A** — um único realm `plataforma` no Keycloak, com três clients:
`analytics-api`, `investigator-api` e `case-manager-api`.

> Nota de grafia: o enunciado grafa o realm como `"platforma"`; adotamos a
> grafia `plataforma` assumindo typo no PDF, mantendo os nomes dos clients
> exatamente como especificados.

### Viés da decisão (o que estamos otimizando)

Toda decisão de arquitetura carrega um viés. O nosso, explicitado:

1. **UX de SSO em primeiro lugar** — o requisito "usuário loga uma vez e acessa
   todas as aplicações permitidas" é inegociável no enunciado. A sessão SSO do
   Keycloak vive no nível do **realm**; portanto qualquer desenho que quebre o
   realm quebra o SSO nativo.
2. **Uma única população de usuários** — João Silva é a mesma pessoa no
   Analytics, no Investigator e no Case Manager. A documentação oficial do
   Keycloak orienta separar realms por *população de usuários* (ex.:
   funcionários vs. clientes externos), não por aplicação: "Realms are isolated
   from one another and can only manage and authenticate the users that they
   control." Aplicações são **clients**: "entities that can request Keycloak to
   authenticate a user [...] and provide a single sign-on solution."
3. **Custo operacional on-premises** — a plataforma é distribuída on-premises
   para órgãos de controle; cada realm adicional multiplica configuração
   (chaves, políticas, temas, eventos) que alguém precisa manter em cada
   instalação. Menos partes móveis = menos erro de operação.
4. **Aderência à documentação oficial** — em uma prova (e em produção), uma
   decisão alinhada à recomendação do fabricante é mais defensável e mais
   fácil de sustentar em upgrades.

### Trade-offs entre as opções

| Critério | Opção A — realm único | Opção B — múltiplos realms |
|---|---|---|
| SSO (login único) | Nativo: uma sessão de realm cobre os 3 clients | Quebrado por padrão: realms são isolados; exigiria duplicar usuários ou identity brokering entre realms |
| Permissões independentes por app | **Client roles**: cada client é um namespace de roles próprio ("basically a role namespace dedicated to the client") | Também funciona, mas com isolamento redundante |
| Revogar acesso a um app sem afetar os demais | Remover o client role do usuário naquele client; nada mais muda | Funciona, a um custo de gestão muito maior |
| Auditoria (qual app, quando) | Eventos por client; claim `azp` identifica o client de origem no token | Funciona |
| Complexidade operacional | 1 realm para configurar, fazer backup, atualizar | 3× configuração + sincronização de usuários entre realms |
| Isolamento máximo (bases de usuários distintas, chaves separadas) | Menor | Maior — é o único cenário em que B vence |

### Quando a Opção B seria a correta

Para sermos honestos com o viés: múltiplos realms venceriam se as aplicações
atendessem **populações de usuários distintas** (ex.: um realm para servidores
do órgão de controle e outro para auditados externos) ou se houvesse exigência
regulatória de isolamento duro entre inquilinos (chaves criptográficas e base
de usuários fisicamente separadas). Não é o nosso cenário: é uma plataforma,
uma organização, uma base de usuários.

Nota de escala (consenso da comunidade Keycloak): cada realm cria recursos
isolados e a performance degrada com centenas de realms — realm-por-aplicação
não escala como padrão de projeto.

### Como o SSO funciona na Opção A

1. Usuário acessa o Analytics → redirecionado ao Keycloak (realm `plataforma`) → autentica.
2. Keycloak cria a **sessão SSO do realm** (cookie de sessão do Keycloak) e
   emite tokens para o client `analytics-api` (claim `azp: analytics-api`).
3. Usuário acessa o Investigator → redirecionado ao Keycloak → a sessão SSO já
   existe → **novo token emitido sem novo login**, agora com `azp: investigator-api`.
4. Cada token carrega apenas os client roles daquele usuário (em
   `resource_access.<client>.roles`), garantindo permissões independentes.

### Como as permissões ficam independentes

- Cada client define seus próprios roles: `analytics-api` → `viewer`, `search`;
  `investigator-api` → `senior-investigator`, `search`; etc.
- Atribuição é por usuário × client. Remover o acesso de João ao Case Manager
  = remover os client roles dele em `case-manager-api`; Analytics e
  Investigator não são tocados.
- O token só inclui em `resource_access` os clients em que o usuário tem
  roles — o JWT carrega **apenas permissões relevantes** (requisito 1.2).

**Fontes:** [Keycloak Server Administration Guide](https://www.keycloak.org/docs/latest/server_admin/index.html)
(conceitos de realm, client e client roles);
[Keycloak forum — single vs multiple realms](https://forum.keycloak.org/t/best-practice-for-multi-user-type-access-single-realm-vs-multiple-realms/31355);
[Cloud-IAM — Keycloak multi-tenancy](https://www.cloud-iam.com/post/keycloak-multi-tenancy).

---

## 1.2 Modelo de Permissionamento

<!-- TODO: desenvolver — armazenamento (client roles no Keycloak), validação na
API (dependency FastAPI extrai e normaliza permissões), JWT enxuto
(resource_access só com clients relevantes), auditoria por aplicação
(tabela search_audit_log + eventos do Keycloak). Referenciar docs/JWT_STRUCTURE.md.

PEGADINHA DO EXEMPLO: "viewer → vê relatórios ASSOCIADOS AO JOÃO" implica
autorização em nível de RECURSO (ownership), que client roles sozinhos não
resolvem. Tratar aqui como conceito (atributo de dono + filtro na query, ou
Keycloak Authorization Services), notando que: (a) a tabela analytics_reports
da Parte 2 não tem coluna de dono — o escopo por recurso NÃO entra no schema
da Parte 2; (b) "modelo de permissões mais granular" é item da Parte 4. -->

## 1.3 Análise de Cenários

<!-- TODO Cenário 1: conceder Analytics a 50 novos usuários sem afetar 300 do
Investigator — grupo "analytics-viewers" com client role mapeado; atribuição em
lote via Admin API; nenhuma mudança toca roles de outros clients. -->

<!-- TODO Cenário 2: chamada API-to-API Investigator → Analytics — service
account (client credentials grant) vs. repassar o JWT do usuário; discutir
rastreabilidade do usuário final vs. limites de permissão do serviço. -->
