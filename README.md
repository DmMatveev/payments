# payments

Асинхронный сервис процессинга платежей. Принимает заявки на оплату, обрабатывает их через эмулируемый платёжный шлюз и уведомляет клиента о результате по webhook.

## Стек

- FastAPI + Pydantic v2
- SQLAlchemy 2.0 (async) + asyncpg
- PostgreSQL 17
- RabbitMQ + FastStream
- Alembic
- Docker / docker-compose

## Архитектура

Слоистая (clean/hexagonal):

- `app/domain` — доменные сущности и value objects (`Payment`, `Money`, `PaymentStatus`, …).
- `app/application` — use cases (`create_payment`, `get_payment`, `process_payment`, `mark_payment_failed`).
- `app/infrastructure` — адаптеры (репозитории, webhook-нотификатор), конфиг, UoW, outbox relay.
- `app/entrypoints` — HTTP (FastAPI) и messaging (FastStream consumer).

### Поток обработки платежа

1. `POST /api/v1/payments` — use case в одной транзакции создаёт запись в `payments` и запись в `outbox`.
2. `outbox_relay` (фоновая задача в API-процессе) пуллит `outbox`, публикует событие `payment.created` в очередь `payments.new`, затем удаляет запись. Защита от дублей через `locked_at`-lease + `SELECT … FOR UPDATE SKIP LOCKED`.
3. Consumer (`app/entrypoints/messaging/worker.py`) получает событие, эмулирует работу шлюза (2–5 секунд, 90% успех / 10% ошибка), обновляет статус и отправляет webhook.
4. При ошибке — ретрай c экспоненциальной задержкой (`2^n`), максимум 3 попытки. После исчерпания — сообщение уходит в DLQ `payments.dlq`.

## Запуск

```bash
docker compose up --build
```

Поднимаются сервисы:

| Сервис    | Порт (host)           |
|-----------|-----------------------|
| api       | `8000`                |
| postgres  | `15432`               |
| rabbitmq  | `5672`, UI `15672`    |

Миграции Alembic накатываются автоматически при старте контейнера `api`.

Swagger: <http://localhost:8000/docs>
RabbitMQ UI: <http://localhost:15672> (guest / guest)

## Конфигурация

Переменные окружения (значения по умолчанию см. в `app/infrastructure/configs/config.py`):

| Переменная        | По умолчанию      | Описание                      |
|-------------------|-------------------|-------------------------------|
| `DB_HOST`         | `localhost`       | Хост Postgres                 |
| `DB_PORT`         | `5432`            |                               |
| `DB_USER`         | `payments`        |                               |
| `DB_PASSWORD`     | `payments`        |                               |
| `DB_NAME`         | `payments`        |                               |
| `RABBITMQ_HOST`   | `localhost`       |                               |
| `RABBITMQ_PORT`   | `5672`            |                               |
| `RABBITMQ_USER`   | `guest`           |                               |
| `RABBITMQ_PASSWORD` | `guest`         |                               |
| `API_KEY`         | `secret-api-key`  | Ключ для заголовка `X-API-Key` |

## Аутентификация

Все эндпоинты требуют заголовок `X-API-Key: <API_KEY>`.

## API

### `POST /api/v1/payments`

Создание платежа.

Заголовки:

- `X-API-Key` — обязательный.
- `Idempotency-Key` — обязательный. Повторный запрос с тем же ключом возвращает уже созданный платёж.

Тело:

```json
{
  "amount": "199.90",
  "currency": "RUB",
  "description": "Order #42",
  "metadata": {"order_id": 42},
  "webhook_url": "https://example.com/webhooks/payments"
}
```

Ответ `202 Accepted`:

```json
{
  "payment_id": "121aec34-2f03-4d53-adf2-c6eb0d2af604",
  "status": "pending",
  "created_at": "2026-04-22T10:15:00.000000Z"
}
```

`payment_id` генерируется сервером и не совпадает с `Idempotency-Key`.

Пример:

```bash
curl -X POST http://localhost:8000/api/v1/payments \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: secret-api-key' \
  -H 'Idempotency-Key: 8e2f1e5a-2a7a-4ab3-9f5d-1e7e8f9a0b3c' \
  -d '{
    "amount": "199.90",
    "currency": "RUB",
    "description": "Order #42",
    "metadata": {"order_id": 42},
    "webhook_url": "https://example.com/webhooks/payments"
  }'
```

### `GET /api/v1/payments/{payment_id}`

Получение детальной информации о платеже.

```bash
curl http://localhost:8000/api/v1/payments/121aec34-2f03-4d53-adf2-c6eb0d2af604 \
  -H 'X-API-Key: secret-api-key'
```

Ответ `200 OK`:

```json
{
  "id": "121aec34-2f03-4d53-adf2-c6eb0d2af604",
  "amount": "199.90",
  "currency": "RUB",
  "description": "Order #42",
  "metadata": {"order_id": 42},
  "status": "succeeded",
  "idempotency_key": "8e2f1e5a-2a7a-4ab3-9f5d-1e7e8f9a0b3c",
  "webhook_url": "https://example.com/webhooks/payments",
  "created_at": "2026-04-22T10:15:00.000000Z",
  "processed_at": "2026-04-22T10:15:03.512000Z"
}
```

## Webhook

После обработки платежа consumer делает `POST` на `webhook_url`:

```json
{
  "payment_id": "121aec34-2f03-4d53-adf2-c6eb0d2af604",
  "status": "succeeded",
  "amount": "199.90",
  "currency": "RUB",
  "processed_at": "2026-04-22T10:15:03.512000Z"
}
```

При сетевых ошибках отправка повторяется до 3 раз с экспоненциальной задержкой.

## Очереди RabbitMQ

- `payments.new` — рабочая очередь (durable, `x-dead-letter-exchange=""`, `x-dead-letter-routing-key=payments.dlq`).
- `payments.dlq` — Dead Letter Queue; сюда попадают сообщения, отклонённые consumer'ом после 3 неуспешных попыток.

## Локальная разработка

```bash
uv sync
docker compose up -d postgres rabbitmq
uv run alembic -c alembic/alembic.ini upgrade head
uv run uvicorn app.main:app --reload
uv run faststream run app.entrypoints.messaging.worker:app
```

## Тесты

```bash
uv run pytest
```
