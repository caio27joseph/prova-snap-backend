# AI Engineering Log

Registro contínuo do uso de IA durante a prova técnica, conforme exigido na Parte 5.
Mantido em tempo real durante o desenvolvimento (não reconstruído ao final).

## 1. Ferramentas utilizadas

- **Claude Code** (Anthropic, modelo Fable 5) — extensão VSCode. Única
  ferramenta de IA utilizada, em três papéis distintos: sessão principal
  (decisões, revisão, orquestração), agentes paralelos em git worktrees
  (implementação dos blocos T-03/T-04 e T-05/T-06/T-07/T-08 em pares
  simultâneos) e agente auditor independente sem o contexto da sessão
  (verificação final contra o PDF).

## 2. Casos em que a IA ajudou (até 3)

### Caso 1: Estruturação inicial do projeto a partir do PDF
- **Problema:** transformar um enunciado de 9 páginas em um plano de trabalho acionável
  sem perder nenhum requisito pontuável.
- **Como a IA ajudou:** extraiu todos os requisitos do PDF para `docs/REQUIREMENTS.md`
  com checklist de Definition of Done, e criou as diretrizes de trabalho (`CLAUDE.md`).
- **Resultado:** visão completa dos 5 blocos da prova e dos critérios de avaliação antes
  de escrever qualquer código. Validação ao final: a auditoria independente
  (Exemplo 3 da seção 5) comparou o extrato com as 9 páginas do PDF e o
  considerou fiel, com um único desvio encontrado e corrigido — a atribuição
  do método HTTP (ver Decisão 4).

### Caso 2: Implementação paralela de dois blocos com agentes em worktrees (2026-08-24)
- **Problema:** T-03 (models + migração + fundação de testes) e T-04 (dependency
  JWT) são blocos grandes e independentes; executá-los em série custaria o
  dobro do tempo de parede.
- **Como a IA ajudou:** após eu isolar a fundação compartilhada (contrato de
  identidade em `app/auth/mock_users.py`, entregue e mergeado antes), dois
  agentes trabalharam simultaneamente em worktrees git separados
  (`scripts/wt.sh`), cada um com lista fechada de arquivos próprios, proibidos
  de commitar (revisão humana antes de cada commit/merge).
- **Resultado:** os dois blocos ficaram prontos em paralelo com **zero
  conflitos de merge** — a análise prévia de acoplamento (fundação primeiro,
  ownership de arquivos disjunto) foi o que tornou o paralelismo seguro.

### Caso 3: Diagnóstico de bug latente de logging escondido pelo Alembic (2026-08-24)
- **Problema:** no bloco T-06, o teste "falha de auditoria não derruba a
  busca" precisava provar via `caplog` que o erro era logado — e o caplog
  capturava **zero** registros mesmo com a falha disparando.
- **Como a IA ajudou:** o agente rastreou a causa até um bug latente que
  ninguém tinha visto: o `fileConfig()` do `alembic/env.py` usa por default
  `disable_existing_loggers=True`, e como o conftest roda as migrações
  **in-process**, ele silenciava todos os loggers da aplicação pela sessão
  inteira de testes — qualquer asserção de logging futura falharia de forma
  misteriosa.
- **Resultado:** correção de uma linha (`disable_existing_loggers=False`, com
  why-comment no `env.py`); o bug nunca teria aparecido em produção (Alembic
  roda em processo separado), mas mascararia testes — a classe de bug mais
  cara de encontrar depois.

## 3. Casos em que a IA estava errada (mínimo 1)

<!-- OBRIGATÓRIO: registrar no momento em que acontecer.
Formato:
- O que foi sugerido:
- Por que a sugestão era problemática:
- Como identifiquei o problema:
- O que decidi fazer em vez disso:
-->

### Caso 1: IA propôs aceitar dois formatos de claim no JWT — sugestão acatada e depois revertida (2026-08-24)
- **O que foi sugerido:** ao levantar as alternativas de formato do claim de
  permissões, a IA (Claude Code) propôs como opção viável aceitar **dois
  formatos** no token (`resource_access` como primário + claim achatado
  `permissions` como fallback), com justificativa dela própria: flexibilidade,
  compatibilidade com o Keycloak real e conveniência para testes. O custo foi
  rotulado apenas como "beira o over-engineering". Acatei a sugestão conforme
  apresentada — a primeira versão da Decisão 2 veio dessa análise da IA.
- **Por que a sugestão era problemática:** a análise omitiu o argumento
  decisivo — em código de **autenticação**, aceitar múltiplos formatos de
  entrada é um anti-pattern conhecido (ser "liberal no que aceita" amplia a
  superfície de ambiguidade e ataque: qual claim vence se ambos existirem e
  divergirem? o que fazer com fallback malformado?). Além disso, os benefícios
  que a própria IA listou eram ilusórios: o emissor mock é controlado por nós,
  então a "conveniência para testes" cabe num helper de uma função, não no
  contrato do token. Um trade-off com lado claramente errado para código de
  segurança foi apresentado como neutro.
- **Como identifiquei o problema:** a detecção partiu de mim. Ao reler o log,
  a decisão me incomodou — flexibilidade extra em código de autenticação
  raramente sai de graça — e, em vez de aceitar a justificativa registrada,
  submeti a sugestão a uma reavaliação adversarial, exigindo que a IA
  defendesse a própria proposta. Sob esse escrutínio a análise dela desmoronou:
  ela mesma passou a apontar que parsing liberal em código de segurança
  invalidava a opção que havia proposto. Fica a lição: sugestões de IA em
  decisões sensíveis precisam ser desafiadas ativamente, mesmo quando a
  análise parece equilibrada.
- **O que decidi fazer em vez disso:** descartei a sugestão e adotei o formato
  único e estrito `resource_access.<client>.roles` (ver Decisão 2), com
  normalização interna na dependency e o claim achatado registrado como
  alternativa rejeitada.

### Caso 2: `str(URL)` do SQLAlchemy mascarou a senha e quebrou o conftest (2026-08-24)
- **O que foi sugerido:** o primeiro `tests/conftest.py` gerado pela IA (agente
  do bloco T-03) montava a URL do banco de teste com `str(make_url(...))` para
  trocar o nome do database.
- **Por que era problemático:** `str(URL)` no SQLAlchemy **mascara a senha como
  `***` literal** por segurança de logging; a URL reutilizada para conectar
  falhava com `FATAL: password authentication failed for user "prova"`.
- **Como o problema foi identificado:** a suíte falhou na primeira execução; o
  agente inicialmente **errou o diagnóstico** (culpou credenciais do Docker)
  antes de localizar a causa real na serialização da URL — dois erros de IA em
  sequência no mesmo incidente, ambos pegos porque a fundação de testes roda
  contra Postgres real (Decisão 3 se pagando).
- **O que foi feito em vez disso:** `render_as_string(hide_password=False)`,
  com why-comment em `tests/conftest.py` para o próximo leitor não repetir o
  ciclo.

### Caso 3: Teste gerado pela IA asseriu o comportamento que a regra proíbe (2026-08-24)
- **O que foi sugerido:** no bloco T-05, a primeira versão do teste obrigatório
  nº 3 (agregação multi-app) esperava `total_matched == 2` para o termo
  "aurora" na seção do Analytics.
- **Por que era problemático:** o segundo "Aurora" do seed existe apenas no
  **título** de um relatório — e a regra do enunciado diz que o Analytics
  busca **somente no conteúdo**. O código implementava a regra corretamente;
  era o teste que assumia o comportamento proibido. Um teste errado que
  "corrige" código certo é o modo de falha mais perigoso de teste gerado por
  IA: a suíte vermelha empurra o desenvolvedor a quebrar a regra para
  "consertar".
- **Como foi identificado:** a falha do teste contra o código correto forçou a
  releitura da regra no enunciado; a expectativa foi corrigida para 1, com
  comentário no teste explicando o porquê do valor.
- **O que foi feito em vez disso:** expectativa corrigida e regra reforçada —
  o mesmo bloco ganhou o teste de vazamento (a seção analytics não contém
  título/conteúdo), tornando a regra "content-only, agregado-only" guardada
  dos dois lados.

## 4. Decisões de Engenharia (mínimo 2)

<!-- Formato:
### Decisão N: <título>
- Alternativas consideradas:
- Decisão tomada:
- Por que foi escolhida:
-->

### Decisão 1: Realm único vs múltiplos realms no Keycloak (2026-08-24)
- **Alternativas consideradas:** (A) realm único `plataforma` com um client por
  aplicação; (B) um realm por aplicação.
- **Decisão tomada:** Opção A.
- **Por quê:** em vez de aceitar a recomendação inicial da IA de bandeja, pedi
  que a decisão fosse fundamentada na **documentação oficial do Keycloak**. A
  doc orienta separar realms por população de usuários (não por app), define
  aplicações como *clients* e client roles como namespace de permissões por
  app; a sessão SSO vive no nível do realm, então a Opção B quebraria o
  requisito de login único. Análise completa, trade-offs e o viés explícito da
  decisão em `docs/PARTE1_AUTH.md` (seção 1.1).

### Decisão 2: Formato do claim de permissões no JWT (2026-08-24, revisada no mesmo dia)
- **Alternativas consideradas:** (a) só `resource_access.<client>.roles`
  (formato real do Keycloak); (b) só claim achatado `permissions:
  ["analytics:search", ...]`; (c) aceitar ambos, com `resource_access` como
  primário e o claim achatado como fallback.
- **Decisão tomada:** (a) — apenas `resource_access`, formato único e estrito.
- **Histórico:** a alternativa (c) foi proposta pela IA, com justificativa de
  flexibilidade, e acatei a sugestão inicialmente. Ao revisar a decisão
  criticamente, ficou claro que código de autenticação deve ser
  **estrito** no que aceita: dois formatos = dois caminhos de parsing em código
  crítico de segurança, com ambiguidades a resolver e testar (e se os dois
  claims estiverem presentes e divergirem? e se o fallback vier malformado?).
  Os benefícios de (c) eram ilusórios — o emissor mock é nosso, então um helper
  de teste `make_token(permissions=[...])` gera `resource_access` com a mesma
  facilidade de um claim achatado. Reversão detalhada na seção 3 (caso de IA
  incompleta/errada).
- **Por quê (a):** fidelidade ao token real do Keycloak (troca futura por
  Keycloak real sem quebrar contrato); superfície mínima de parsing na
  dependency; o enunciado pede que a dependency *produza* `permissions`, não
  que o token carregue um claim achatado. A dependency normaliza
  `resource_access.<client>.roles` para a lista interna `<app>:<role>` e o
  resto do código desconhece o formato do token. Estrutura documentada em
  `docs/JWT_STRUCTURE.md`.

### Decisão 3: Banco de testes — Postgres real via Docker, contra a recomendação da IA (2026-08-24)
- **Alternativas consideradas:** SQLite in-memory (recomendação da IA:
  zero-setup, suite rápida); fixture Postgres via Docker; híbrido com variável
  de ambiente.
- **Decisão tomada:** fixture Postgres via Docker.
- **Por quê rejeitei a recomendação:** o docker-compose com Postgres já é
  pré-requisito para rodar a aplicação, então exigir Docker nos testes não
  adiciona fricção real ao avaliador — e testar no mesmo engine de produção
  elimina divergências de dialeto (comportamento de `ILIKE`, JSON/JSONB,
  collation) exatamente na feature central da prova, que é busca. Fidelidade >
  velocidade de suite neste contexto.

### Decisão 4: Contrato do endpoint de busca (2026-08-24)
- **Escopo da busca:** todas as aplicações para as quais o usuário tem
  `<app>:search` (agregação por padrão). O `azp` identifica o app de origem
  para auditoria, mas não restringe o escopo — leitura mais direta do teste
  obrigatório "usuário com 2 permissões recebe resultados agregados".
- **Formato da agregação:** resultados agrupados por app
  (`results.analytics / .investigator / .case_manager`), porque cada app
  retorna um shape deliberadamente diferente (agregado / completo / metadados)
  e um envelope único achatado seria perda de informação.
- **Método HTTP:** POST com body JSON (a IA recomendou GET pela semântica de
  leitura). Escolhi POST para deixar o contrato aberto a busca rica (filtros
  estruturados no body) sem quebra futura, com o bônus de não expor o termo
  pesquisado em query string de logs de proxy — relevante numa plataforma
  forense. *Correção de atribuição (2026-08-24, achada por auditoria
  independente):* esta decisão dizia originalmente "o enunciado permite
  POST/GET" — mas o PDF **não especifica método algum**; o "POST/GET" tinha
  sido inventado pelo nosso extrato (`docs/REQUIREMENTS.md`) e citado aqui
  como se fosse o enunciado. A escolha do POST permanece válida pelos motivos
  acima; o que estava errado era atribuí-la a uma permissão do enunciado. O
  erro só apareceu quando um agente auditor sem o contexto da sessão comparou
  o extrato com o PDF original — evidência de que extratos viram fonte de
  verdade silenciosamente e precisam de auditoria independente.
- **Índices:** B-tree apenas nas colunas de filtro
  (`investigator_entities.type`, `case_manager_cases.assigned_to`/`status`,
  `search_audit_log(user_id, timestamp)`). Sem índice trigram nos campos de
  texto: `ILIKE '%termo%'` não usa B-tree e `pg_trgm` é exatamente a "busca
  otimizada" que o enunciado exclui do escopo — vai para a Parte 4 como
  melhoria priorizada.

### Decisão 5: Escalabilidade — UUIDv7 como PK e preparação para cursor/shard sem implementá-los (2026-08-24)
- **Contexto:** questionei se a solução escalava
  Diagnóstico: API stateless escala em leitura, mas não havia
  paginação, `ILIKE` faz seq scan e IDs seriais colidem entre shards.
- **Alternativas consideradas:** (a) UUIDv7 como PK; (b) BIGSERIAL com cursor
  composto `(created_at, id)`; (c) BIGINT estilo Snowflake com gerador próprio.
- **Decisão tomada:** UUIDv7 gerado na aplicação (pacote `uuid-utils`;
  Python 3.12 não tem `uuid7` nativo) + LIMIT interno fixo na busca +
  envelope de resposta por app já comportando `next_cursor` futuro.
  Paginação por cursor NÃO é implementada agora: o enunciado a lista
  explicitamente como melhoria da Parte 4, e o rubric premia não construir
  feature não pedida.
- **Por quê:** UUIDv7 resolve os dois problemas com uma decisão só — é
  ordenável por tempo (cursor keyset `id > :cursor ORDER BY id` estável sob
  inserções) e globalmente único sem coordenação (cada shard gera IDs sem
  colisão), com boa localidade de B-tree, ao custo de 16 bytes vs 8 do BIGINT.
  Trocar o tipo da PK depois, com dados vivos, é das migrações mais caras que
  existem — é a decisão barata-agora/cara-depois clássica. O caminho de shard
  já é natural no design: strategy per app + resposta agrupada = primeiro
  corte é funcional (um banco por domínio) sem mudar o contrato do endpoint.
  Estratégia completa em `docs/ESCALABILIDADE.md`.

### Decisão 6: Design da trilha de auditoria (2026-08-24)
- **Contexto:** a decisão de buscar em todas as apps permitidas (Decisão 4)
  separou dois conceitos que o schema do enunciado funde na coluna `app`: o
  app de *origem* (azp do token) e os apps *pesquisados* (dados tocados).
- **Granularidade — 1 linha por app pesquisada:** busca que varre 3 apps gera
  3 linhas, cada uma com `app` = domínio de dados acessado. É o formato que
  responde à pergunta forense central ("quem acessou dados do Investigator
  este mês?") com um WHERE simples. Alternativas rejeitadas: linha única com
  origem (perde quais dados foram tocados) e lista serializada numa string
  (anti-padrão em tabela de auditoria).
- **Schema — extensão rica, contra a recomendação da IA:** a IA recomendou
  estender minimamente (só `origin_app`); decidi incluir também
  `results_count` e `status`. Motivo: numa plataforma forense a trilha É o
  produto — contagem de resultados e status transformam a tabela numa fonte
  de resposta a perguntas de compliance ("busca negada?", "quantos registros
  viu?") sem join com nada. O custo (colunas a mais e testes) é aceito
  deliberadamente; a extensão é aditiva sobre as colunas do enunciado e será
  justificada em comentário na migration.
- **Tentativas negadas — no DB também (403 sim, 401 não):** questionei a
  recomendação da IA de manter negados só no log de aplicação — os dois logs
  existirão de qualquer forma, e com a coluna `status` a linha de negado é
  semanticamente limpa. Fronteira mantida: **403** (identidade verificada,
  permissão ausente) gera linha `app=NULL, origin_app=azp, status='denied',
  results_count=NULL`; **401** (token inválido/forjado) NUNCA escreve no DB —
  identidade não verificada significaria ator não-autenticado escrevendo na
  trilha com user_id forjado (poluição + vetor de escrita). 401 fica no log
  de aplicação. Nota: no nosso modelo de escopo não existe negação parcial —
  403 só ocorre quando o usuário não tem nenhuma permissão de busca.
- **Fixado previamente (CLAUDE.md), documentado aqui:** a escrita de
  auditoria é síncrona, em sessão separada da busca, e falha de auditoria
  nunca quebra a resposta (capturada e logada como erro). Trade-off assumido:
  disponibilidade > completude da trilha; a alternativa audit-or-deny (sem
  trilha, sem resposta) é defensável em contexto forense e fica registrada
  como melhoria possível. Teste obrigatório prova a linha gravada no sucesso.

### Decisão 7: Convenções de corretude fixadas antes do código (2026-08-24)

Três detalhes com resposta convencional correta — fixados como convenção (não
houve rodada de opções; a decisão aqui é *tê-los tratado deliberadamente*),
cada um com comentário no código e teste dedicado:

- **Curingas do LIKE são escapados — input do usuário é sempre literal.**
  Helper único `escape_like()` escapa `\`, `%` e `_` e o `ilike()` recebe
  `escape="\\"`. Sem isso, buscar `100%` casaria com tudo que começa com
  "100" — bug de corretude (não é SQL injection; parâmetros já cobrem isso).
  Decisão semântica: não expomos busca por curinga ao usuário. Teste: seed
  com "100%" e "1000"; buscar `100%` retorna só o literal.
- **Tempo em `timestamptz` UTC com default no servidor.** Todas as colunas
  `DateTime(timezone=True)` + `server_default=func.now()` — o banco é a fonte
  da verdade temporal (N instâncias = N relógios; default no servidor elimina
  skew na trilha de auditoria). Nenhum datetime naive no app. O timestamp
  embutido no UUIDv7 é detalhe de ordenação do ID, não fonte de tempo —
  `created_at` responde perguntas temporais.
- **Serialização como fronteira de segurança.** Um response model Pydantic
  por app ligado via `response_model`: no `AnalyticsAggregate` os campos
  `title`/`content` dos reports **não existem** no schema — "sem detalhe
  sensível" vira impossibilidade estrutural, não disciplina de quem lembra de
  não incluir. Case Manager: ILIKE só em `title` (regra "sem busca em
  conteúdo" vive no strategy). Teste de vazamento (asserção negativa): a
  seção analytics da resposta não contém chaves de conteúdo de report.

### Decisão 8: SQLAlchemy síncrono — decisão enviesada pela documentação do FastAPI (2026-08-24)
- **Alternativas consideradas:** (a) engine síncrona (psycopg3) com endpoints
  `def`; (b) AsyncSession + asyncpg com `async def` em tudo (permitiria rodar
  as 3 strategies com `asyncio.gather`); (c) híbrido.
- **Decisão tomada:** (a) síncrono — e registro explicitamente o viés: a
  decisão segue a orientação da própria documentação do FastAPI
  (fastapi.tiangolo.com/async): *"If you just don't know, use normal `def`"*;
  endpoints `def` rodam em threadpool externo ("run in an external threadpool
  that is then awaited... as it would block the server") e *"in any of the
  cases above, FastAPI will still work asynchronously and be extremely fast"*.
- **Por quê:** menos partes móveis exatamente onde a prova pontua — fixtures
  de teste triviais (sem pytest-asyncio/greenlet), sem armadilhas de lazy-load
  em contexto async, ~1h a menos do orçamento de 6-8h. O ganho real do async
  (fan-out concorrente das 3 buscas) é irrelevante com LIMIT fixo e volume de
  prova; fica anotado para a Parte 4 como melhoria com custo/benefício.

### Decisão 9: Taxonomia de auth, formato de identidade e agregado do Analytics (2026-08-24)
- **401 vs 403 (e azp desconhecido → 401):** 401 = token não confiável (sem
  header, malformado, assinatura inválida, expirado, claims obrigatórios
  ausentes, **azp fora dos 3 clients conhecidos**); 403 = token confiável sem
  nenhuma permissão `<app>:search`. Espelha o Keycloak real (client
  desconhecido falharia na validação de audience). Regra única: 401 se decide
  antes de olhar permissões, 403 depois — e mantém limpa a regra de auditoria
  da Decisão 6 (403 audita no DB; 401 nunca).
- **Identidade = UUID do claim `sub`:** `assigned_to` e `user_id` da
  auditoria armazenam o `sub` do Keycloak. Alternativa rejeitada: username
  (`preferred_username` é mutável — rename quebraria atribuições e trilha).
  Seed usa UUIDs fixos de usuários de teste documentados, reutilizados pelo
  helper de tokens mock — o teste do Case Manager fecha por construção.
- **Agregado do Analytics = total + distribuição por mês:** `total_matched` +
  `by_month` (COUNT + GROUP BY date_trunc de `created_at`). Zero conteúdo
  exponível — nem títulos, que em contexto forense já são detalhe sensível
  ("Investigação Empresa X"). Interpretação deliberada de um requisito que o
  enunciado deixa aberto ("dados agregados, sem detalhe sensível").

### Decisão 10: PyJWT em vez de python-jose — revisita deliberada após releitura do PDF (2026-08-24)
- **Contexto:** releitura do PDF original para conferência final. O enunciado
  cita python-jose apenas como exemplo ("biblioteca python-jose **ou
  outra!**") — não é mandato. Critério que defini: se fosse citação com
  alternativa explícita, escolheríamos a melhor lib e documentaríamos.
- **Alternativas:** python-jose (citada, fixada inicialmente no CLAUDE.md) vs
  PyJWT.
- **Decisão tomada:** PyJWT.
- **Por quê:** python-jose teve CVEs em 2024 (CVE-2024-33663, confusão de
  algoritmo; CVE-2024-33664, DoS via JWE) e manutenção irregular; PyJWT é
  ativamente mantida, com API menor e mais estrita — coerente com a postura
  de parsing estrito da Decisão 2 e com o contexto forense. As CVEs não
  afetam diretamente HS256 puro, mas entre duas libs equivalentes para o
  nosso uso, a de melhor postura de segurança vence. CLAUDE.md atualizado.

### Decisão 11: Monólito modular, não microserviços (2026-08-24)
- **Contexto:** questionei se as 3 aplicações não deveriam ser 3 serviços.
- **Decisão tomada:** um único serviço FastAPI (monólito modular), com as
  costuras de extração prontas por desenho.
- **Por quê:** o enunciado pede um endpoint de busca *compartilhado* (as 3
  "aplicações" são clients/produtos que consomem o backend, não serviços a
  construir); on-premises, cada serviço extra é custo operacional do cliente;
  busca agregada + trilha de auditoria única virariam problemas distribuídos
  sem ganho no volume atual. O strategy per app, a resposta agrupada
  (scatter-gather) e o caminho de shard funcional já deixam a extração barata
  se um domínio um dia precisar de deploy/escala independente — critério
  objetivo registrado em `docs/ESCALABILIDADE.md` (seção "Por que um serviço
  único").

### Decisão 12: As 3 melhorias da Parte 4 — FTS → Paginação → Observabilidade (2026-08-24)
- **Contexto:** decisão tomada deliberadamente DEPOIS da implementação, para
  ser argumentada com dores reais do código entregue e não no vácuo.
- **Alternativas consideradas:** trocar observabilidade por rate limiting
  (proteção ativa contra o cenário da Parte 3); trio conservador
  paginação + CI + mais testes.
- **Decisão tomada:** 1º busca full-text/pg_trgm, 2º paginação por cursor,
  3º OpenTelemetry.
- **Por quê:** (1º) o ILIKE seq scan é o gargalo *conhecido e documentado*
  desde a Decisão 4, e a análise do incidente da Parte 3 é o dado de
  priorização; (2º) a paginação é o maior valor por hora do backlog — o
  schema já está cursor-ready por design (Decisão 5), falta só o endpoint —
  e vem depois do FTS porque paginar um scan lento continua escaneando;
  (3º) a Parte 3 expôs que detectaríamos incidente pelo sintoma, não por
  alerta. Rate limiting rejeitado nesta rodada: sem observabilidade é
  proteção às cegas, e há mitigação temporária no proxy. Argumentação
  completa em `docs/PARTE4_TRADEOFFS.md`.

## 5. Exemplos de interações com IA (opcional, até 3)

Três interações curtas que mostram o processo de trabalho — os transcritos
completos vivem no histórico das sessões; aqui ficam os trechos que importam.

### Exemplo 1: Exigindo fundamentação em documentação oficial (Decisão 1)

A IA apresentou as opções de realm com uma recomendação pronta. Em vez de
aceitar, respondi:

> *"lets use the documentation to find the best approach for this scenario"*

A IA então buscou a documentação oficial do Keycloak e voltou com citações
literais ("Realms are isolated from one another...", clients como "role
namespace dedicated to the client") que fundamentaram a Opção A — e a
resposta da Parte 1.1 cita essas fontes, não a opinião da ferramenta.

### Exemplo 2: Reavaliação adversarial que derrubou uma decisão (Seção 3, Caso 1)

Depois de aceitar a sugestão de dois formatos de claim no JWT, a releitura do
log me incomodou e desafiei:

> *"do you think this is the best?"*

Sob escrutínio, a própria IA apresentou o argumento que invalidava a opção
que havia proposto (parsing liberal em código de autenticação é anti-pattern)
— a decisão foi revertida para o formato único estrito. Lição registrada:
análise de IA em decisão sensível precisa ser desafiada ativamente.

### Exemplo 3: Auditoria independente sem o contexto da sessão

Ao final do desenvolvimento, pedi verificação por um agente limpo:

> *"use a agent to verify the requirements if matches the docs, i want to
> verify without this session context"*

O auditor (sem acesso ao contexto da conversa) releu as 9 páginas do PDF,
executou a suíte (71 testes) e comparou entregável por entregável. Veredito:
tudo atendido — e um achado que ninguém com o contexto da sessão pegaria: o
"POST/GET" citado na Decisão 4 como permissão do enunciado tinha sido
inventado pelo nosso próprio extrato (o PDF não especifica método). Correção
registrada na Decisão 4; a lição — extratos viram fonte de verdade
silenciosamente — fecha o ciclo do uso crítico de IA que esta prova avalia.
