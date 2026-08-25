# Public callback CORS contract

`SplitCORSMiddleware` содержит immutable allowlist только для пары
`POST /api/callback_requests`. Actual request и preflight классифицируются по
точному ASGI path; для preflight effective method берётся из
`Access-Control-Request-Method`.

| Origin / request | Result |
|---|---|
| consumer, exact POST preflight | `200`, ACAO `*`, methods `POST, OPTIONS`, headers `Content-Type, X-Equestrian-Service-Key`, max-age `600`, без credentials |
| consumer, exact actual POST | application status (`201`/`401`/`422`) + ACAO `*`, без credentials |
| CMS allowlisted origin | reflected ACAO, credentials, `Vary: Origin` |
| unknown public requested header | `400`, без ACAO |
| другой write/path | прежний strict CORS |
| request без `Origin` | CORS headers не добавляются |

Selector и body validation выполняются после CORS middleware и не входят в
CORS-классификацию.

## PostgreSQL discovery evidence (2026-08-25)

Перед дальнейшими live smoke была повторена read-only discovery-проверка:

```text
primary labels project=eqsitecms + service=db: no match
fallback exact name: eqsitecms-db
container id: 7c720ddc783d
image: postgres:16
compose project label: eqsitecms-core
compose service label: db
POSTGRES_DB: eqsitecms
POSTGRES_USER: eqsitecms
published port: 5433 -> 5432/tcp
network aliases: eqsitecms-db, db
```

Evidence получен свежими `docker ps` и `docker inspect`; пароль и прочие secret
values не выводились и не фиксировались. Эти значения являются диагностическим
snapshot, а не конфигурацией или хардкодом для тестов.
