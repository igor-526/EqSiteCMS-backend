# Backend

Сервис бэкенда EqSiteCMS — основной API-сервер, обрабатывающий запросы от фронтенда и сайтов-потребителей.

## Стек

- Python 3.14.6
- FastAPI
- SQLAlchemy Core + asyncpg
- PostgreSQL 17
- Alembic
- NATS JetStream
- Sentry (опционально)
- Prometheus (production metrics во внутренней сети)

## Архитектура

```text
src/
├── api/             # HTTP-контракты (роутеры)
├── clients/         # внешние клиенты (NATS, etc.)
│   └── nats/        # NATS JetStream клиент и издатели
├── containers/      # DI-контейнер (dependency-injector)
├── core/            # сущности, схемы, протоколы и бизнес-логика
├── depends/         # сборка зависимостей FastAPI
├── models/          # SQLAlchemy Core tables
├── repositories/    # реализации repository protocols
├── migration/       # Alembic
├── utils/           # База данных и инфраструктурные утилиты
├── main.py
└── settings.py
```

## Запуск в Docker

```bash
cp .env.example .env
docker compose up --build
```

Compose дождётся PostgreSQL, применит миграции и запустит API на `http://localhost:8000`.
Swagger доступен на `http://localhost:8000/docs`.
Контейнеры объединяются в Compose-проект. Каталог `src` подключён как bind mount,
а Uvicorn автоматически перезапускает приложение при изменении исходного кода.

## Локальная разработка

```bash
cp .env.example .env
uv sync
docker compose up -d db nats
uv run alembic -c src/alembic.ini upgrade head
uv run uvicorn main:app --app-dir src --reload
```

```bash
make format
make lint
make test
```

## Интеграция Яндекса

`YANDEX_SERVICE_URL` — базовый URL приватного `yandex-service`, по умолчанию
`http://eqsitecms-yandex-service:8000` (см. `.env.example`). Peer credential не
передаётся; production требует сетевой изоляции peer. Backend обращается к
Метрике только через этот сервис. Tenant определяется сессией пользователя;
все восемь `/api/yandex/**`, включая `POST auth/code`, требуют строго `SEO`.
OAuth exchange не является публичным callback API.

## Доступ SEO и локальный smoke-профиль

Все 11 `/api/seo/**` и 8 `/api/yandex/**` требуют сессию и точную роль
`SEO`: anonymous/невалидная сессия — `401`, ADMIN/SUPERUSER/DEVELOPER/
USER_MANAGER без SEO и пустые scopes — `403` до peer и чтения тела.
SEO-only и SEO+ADMIN допускаются; административного override нет.
GET — исключения из Public Read: приватная аналитика, настройки и OAuth/PII.
Tenant берётся только из сессии, selector клиента игнорируется; чужие
blacklist/account UUID дают `404`, чужой OAuth state — `403`.
DTO, validation `400`, duplicate `409`, peer `502`, parse queue `503` сохранены.
Полная матрица: [generated inventory](docs/backend-route-inventory.md).

Peer API остаются Internal Trusted Network без пользовательских ролей и
credentials. Backend не пересылает cookie/Authorization. Peer и БД должны быть
изолированы от внешних callers до production; публичные consumer GET не меняются.

Seed SEO применяется штатным startup seeder. Действующим операторам роль
назначается явно через существующее управление scopes, без массового backfill.
Backend и CMS разворачиваются согласованно; переходного SEO OR ADMIN нет.

Только для локальной тестовой БД после seed, из `services/backend`:

```bash
PYTHONPATH=src uv run python -m maintain.provision_seo_smoke_user \
  --confirm-local-test-db --equestrian-id <UUID-существующей-тестовой-конюшни> \
  --credentials ../../.agents/skills/api-smoke-test/credentials.json \
                ../../.claude/skills/api-smoke-test/credentials.json
```

Команда создаёт active `seo` только с SEO, читает пароль через `password_ref=admin`
из каждого локального файла в памяти (оба пароля должны совпадать), штатно хеширует
и использует одну транзакцию с advisory lock. Пароль/DSN не передавать в shell и
не публиковать. Совместимый повтор — no-op без смены пароля; конфликт
username/tenant/roles/status — отказ без overwrite. Это не startup provisioning.

Откат: согласованно вернуть предыдущие backend и CMS. Неиспользуемый seed SEO
можно оставить; реальные назначения/пользователей автоматически не удалять.
Локальную fixture удаляет оператор только после проверки сохранённых ID
пользователя, tenant и связей, не по одному username; evidence хранить без секретов.

## API

| Метод | Путь | Назначение | Доступ |
|-------|------|------------|--------|
| GET | `/health` | Healthcheck | Public |
| POST | `/api/callback_requests` | Создание заявки (`name` ≤127, `phone` 1..63, `comment` ≤2000; `X-Equestrian-Service-Key` обязателен) | Public write exception |

### CORS для публичной callback-формы

Только точный runtime route `POST /api/callback_requests` является публичным
CORS write-исключением. Для consumer origin preflight разрешает `POST, OPTIONS`
и заголовки `Content-Type`, `X-Equestrian-Service-Key`, отвечает с
`Access-Control-Allow-Origin: *` без credentials. Неизвестный requested header
отклоняется. CMS origins по-прежнему получают reflected origin, credentials и
`Vary: Origin`. Trailing slash, detail/service routes, похожие prefixes и любые
иные write-запросы остаются в strict CORS режиме.

Tenant selector не является авторизацией и продолжает проверяться application
слоем: missing/invalid selector возвращает `401`, структурно неверное тело —
`422`. CORS-заголовок добавляется также к этим ответам, чтобы consumer мог их
прочитать; payload, БД и NATS-контракты middleware не изменяет.

## NATS JetStream

Backend выступает в роли **Publisher** — публикует события в NATS JetStream.

| Stream | Subject | Назначение | Роль |
|--------|---------|------------|------|
| SITE_EVENTS | events.site.callback.requested | Публикация события запроса обратного звонка | исходящий |

### Конфигурация

| Переменная | Описание | Значение по умолчанию |
|------------|----------|----------------------|
| `NATS_SERVERS` | Список серверов NATS (через запятую) | `nats://localhost:4222` |
| `NATS_STREAM_SITE_EVENTS` | Имя stream для событий сайта | `SITE_EVENTS` |
| `NATS_SUBJECT_CALLBACK_REQUESTED` | Subject для событий обратного звонка | `events.site.callback.requested` |

Sentry включается через `SENTRY_ENABLED=true` и `SENTRY_DSN`. В production
Prometheus доступен внутри контейнера на `:9000/metrics`; port не публикуется на
host. Полная матрица настроек, проверка и rollback описаны в
[`docs/operations/observability.md`](../../docs/operations/observability.md).
