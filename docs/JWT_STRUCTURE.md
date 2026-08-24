# Estrutura do JWT esperado

Contrato do token aceito pelo `/api/v1/search`. O Keycloak é **mockado**
(permitido pelo enunciado): assinamos com HS256 e um segredo compartilhado,
mas o **payload espelha fielmente um access token real** do Keycloak — trocar
o mock por um Keycloak real muda a verificação de assinatura, não o contrato.

## Exemplo completo

Header:

```json
{ "alg": "HS256", "typ": "JWT" }
```

Payload (João Silva, logado via Analytics):

```json
{
  "iss": "http://keycloak.local/realms/plataforma",
  "sub": "01a03323-fe61-72b0-9ac6-84f42896edd4",
  "azp": "analytics-api",
  "iat": 1756000000,
  "exp": 1756003600,
  "preferred_username": "joao.silva",
  "resource_access": {
    "analytics-api":    { "roles": ["viewer", "search"] },
    "investigator-api": { "roles": ["senior-investigator", "search"] }
  }
}
```

## Claims e o que a API valida

| Claim | Papel | Validação na dependency |
|---|---|---|
| `sub` | Identidade do usuário (UUID) — vira `user_id` na auditoria e casa com `assigned_to` | Obrigatório; ausente → **401** |
| `azp` | Client que emitiu o token = **app de origem** (auditoria) | Obrigatório; fora dos 3 clients conhecidos → **401** |
| `exp` / `iat` | Janela de validade (TTL de 1h no mock) | Expirado → **401** |
| `resource_access.<client>.roles` | Permissões por aplicação (client roles) | Obrigatório; normalizado para `<app>:<role>` (ex.: `analytics:search`) |
| `iss`, `preferred_username` | Contexto informativo no mock | Não validados no mock (com Keycloak real, `iss` seria) |

**Formato único e estrito** (Decisão 2 do AI log): apenas `resource_access` é
aceito como fonte de permissões — sem claim achatado alternativo. Código de
autenticação é deliberadamente estrito no que aceita.

A dependency produz o que o enunciado pede: `user_id` (`sub`),
`app_client_id` (`azp`) e `permissions` (lista normalizada `<app>:<role>`).

## Taxonomia de erros (Decisão 9)

```
401 Unauthorized  — o token não é confiável (decidido ANTES de olhar permissões)
├─ sem header Authorization / esquema não-Bearer
├─ token malformado (não é JWT)
├─ assinatura inválida
├─ token expirado
├─ claims obrigatórios ausentes (sub, azp, resource_access)
└─ azp fora dos clients conhecidos (analytics-api, investigator-api, case-manager-api)

403 Forbidden     — token confiável, autorização insuficiente
└─ nenhuma permissão <app>:search em nenhuma aplicação
```

401 nunca gera linha na trilha de auditoria (identidade não verificada);
403 gera (Decisão 6).

## Usuários de teste (mock)

Definidos em `app/auth/mock_users.py` (UUIDs fixos, compartilhados pelo seed
e pelos testes — módulo que não existiria com Keycloak real):

| Persona | `sub` (…sufixo) | Permissões de busca | Papel nos testes |
|---|---|---|---|
| `joao.silva` | `…84f42896edd4` | analytics + investigator | Agregação multi-app (teste obrigatório 3) |
| `maria.santos` | `…8509308c7812` | analytics | Só dados do Analytics (teste 1) |
| `pedro.lima` | `…851101980d40` | investigator | Só dados do Investigator (teste 2) |
| `ana.costa` | `…8524ead7cf87` | case-manager | Vê apenas os próprios casos |
| `carlos.souza` | `…853dbd1aa14c` | nenhuma | **403** (teste 4) |
| `outro.usuario` | `…85486f005be6` | case-manager | Dono dos casos que a Ana NÃO pode ver |

## Mock vs. Keycloak real

| Aspecto | Mock (esta prova) | Keycloak real |
|---|---|---|
| Assinatura | HS256, segredo em `.env` | RS256, chave pública via JWKS (`/realms/plataforma/protocol/openid-connect/certs`), com rotação |
| Emissão | Helper de teste `make_token(...)` | Authorization Code Flow + sessão SSO do realm |
| Validação de `iss`/`aud` | Não aplicada | Aplicada contra o realm configurado |
| Revogação | Só por expiração | Logout de sessão / revogação no realm |

A dependency isola essa diferença: só a etapa "verificar assinatura e claims"
mudaria — o resto do código consome `AuthContext` e não sabe qual dos dois
emitiu o token.
