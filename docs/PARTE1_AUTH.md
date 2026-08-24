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

Exemplo do enunciado — João Silva:

```
João Silva (sub: 01a03323-…-84f42896edd4)
├── Analytics:     role "viewer"              → vê relatórios associados a ele
├── Investigator:  role "senior-investigator" → acesso total
└── Case Manager:  SEM ACESSO
```

### Como armazenar as permissões?

Como **client roles no Keycloak** — cada client define seu namespace de roles
(`analytics-api`: `viewer`, `search`; `investigator-api`:
`senior-investigator`, `search`; `case-manager-api`: `search`, `manager`), e a
permissão é a **atribuição usuário × client role**. João tem roles nos dois
primeiros clients e nenhuma no terceiro — "sem acesso" é a *ausência* de
atribuição, não uma regra de negação. Para atribuição em massa, **grupos** com
role mapping (ver Cenário 1). A nossa API **não armazena permissões**: elas
viajam no token, e a fonte da verdade é o Keycloak.

### Como a API valida se o usuário pode acessar um endpoint X?

Uma dependency FastAPI executada antes de qualquer lógica de negócio:

1. Extrai o Bearer token e valida **estritamente**: assinatura, expiração,
   claims obrigatórios (`sub`, `azp`, `resource_access`), `azp` entre os
   clients conhecidos. Qualquer falha → **401** (token não confiável).
2. Normaliza `resource_access.<client>.roles` para permissões internas
   `<app>:<role>` e produz um `AuthContext(user_id, origin_app, permissions)`.
3. O endpoint declara o que exige. No `/search`: ter ao menos um
   `<app>:search`; nenhum → **403**. O escopo da busca = apps com permissão.

Regra de ouro da taxonomia (Decisão 9 do AI log): **401 se decide antes de
olhar permissões; 403 depois** — e 401 nunca gera linha de auditoria
(identidade não verificada), 403 gera. Detalhes em
[`JWT_STRUCTURE.md`](JWT_STRUCTURE.md).

### Como fazer o JWT carregar apenas permissões relevantes?

Esse é o comportamento **default** do Keycloak: `resource_access` inclui
somente os clients em que o usuário tem roles. O token do João carrega
`analytics-api` e `investigator-api` — `case-manager-api` simplesmente não
aparece. Para tokens ainda mais enxutos, **client scope mappings** restringem
quais roles cada client pode receber no token que emite (ex.: o token emitido
para o Analytics não precisa carregar roles do Investigator). No mock
espelhamos o default, que já cumpre o requisito.

### Como implementar auditoria de acessos por aplicação?

Em duas camadas complementares:

- **Keycloak (autenticação):** login events por client — "João autenticou via
  `analytics-api` às 14h" — habilitados no realm, exportáveis via SPI.
- **Aplicação (uso dos dados):** nossa `search_audit_log`, desenhada na
  Decisão 6: **uma linha por app pesquisada** (`app` = domínio de dados
  tocado, `origin_app` = azp de onde o usuário veio, `status`,
  `results_count`). Responde tanto "que apps João acessou e quando" quanto a
  pergunta forense mais forte: "quem viu dados de qual domínio".

### A pegadinha do exemplo: "vê relatórios associados ao João"

O role `viewer` responde **o que João pode fazer** (buscar/ver relatórios) —
mas "*associados ao João*" é autorização em nível de **recurso** (ownership),
que client roles sozinhos não expressam. A solução padrão: o recurso carrega
um atributo de dono (`owner_id = sub`) e a query filtra por ele — exatamente o
padrão que o Case Manager usa com `assigned_to` na Parte 2. A alternativa
pesada seria Keycloak Authorization Services (UMA, políticas por recurso) —
poder que este cenário não justifica. Honestidade de escopo: a tabela
`analytics_reports` da Parte 2 **não tem coluna de dono**, então o filtro de
ownership do Analytics fica como conceito aqui e não entra no schema; um
"modelo de permissões mais granular" é candidato declarado da Parte 4.

## 1.3 Análise de Cenários

### Cenário 1 — 50 usuários novos no Analytics, 300 existentes no Investigator

Com client roles, os namespaces são **isolados por construção**: nada que se
faça em `analytics-api` toca roles de `investigator-api`. O procedimento:

1. Criar (uma vez) o grupo `analytics-users` com role mapping para
   `analytics-api: viewer, search`.
2. Adicionar os 50 usuários ao grupo — em lote via Admin API
   (`PUT /admin/realms/plataforma/users/{id}/groups/{groupId}`), num script
   idempotente; usuários novos podem já nascer no grupo (default group ou
   provisionamento SCIM/LDAP).
3. Validar com um usuário-piloto antes do lote; admin events do Keycloak
   registram cada atribuição (trilha do onboarding).

Os 300 do Investigator não são tocados: nenhuma atribuição deles muda, nenhuma
sessão é invalidada, e o token deles nem menciona `analytics-api`. O grupo
ainda torna o futuro *offboarding* simétrico: remover do grupo revoga o
Analytics inteiro sem efeito colateral.

### Cenário 2 — Investigator chama endpoint do Analytics (API-to-API)

**Decisão: service account (client credentials grant) com propagação da
identidade do usuário final para auditoria.**

O client `investigator-api` habilita seu service account e obtém, via client
credentials, um token **próprio** com roles mínimos (`analytics-api: search` e
nada mais). As alternativas e o porquê:

| Abordagem | Prós | Contras |
|---|---|---|
| **Service account (escolhida)** | Permissões do serviço explícitas e mínimas; funciona sem sessão do usuário (jobs, filas); TTL curto e renovação automática | Perde a identidade do usuário final — precisa de propagação explícita |
| Repassar o JWT do usuário | Identidade fim-a-fim de graça | Acopla a chamada à expiração da sessão do usuário; quebra em processamento assíncrono; o serviço herda permissões que não precisa (blast radius maior); o Analytics não distingue chamada direta de chamada intermediada |
| Token exchange (RFC 8693) | Meio-termo maduro: troca o token do usuário por um de audiência restrita | Mais configuração no Keycloak; valor real só quando muitos serviços se chamam — over-engineering para 3 apps |

A perda de identidade do service account é resolvida por **propagação
explícita**: a chamada leva o `sub` do usuário original (header
`X-On-Behalf-Of` ou claim custom), e a auditoria do Analytics grava **os
dois** — `service_account_investigator` (quem chamou) e o usuário em nome de
quem (accountability forense). Importante: o Analytics **autoriza pelo token
do serviço**, nunca pelo header — o header é rastreabilidade, não credencial.
