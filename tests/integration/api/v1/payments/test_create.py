import uuid
from decimal import Decimal
from http import HTTPStatus

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.db.models import OutboxRow, PaymentRow

# Тест-кейсы:
# 1. Успешное создание платежа — возвращается 202 с payment_id, status, created_at
# 2. Платеж сохраняется в БД с корректными полями
# 3. При создании платежа создается outbox-сообщение
# 4. Повторный запрос с тем же Idempotency-Key возвращает тот же платеж
# 5. Запрос без X-API-Key — 422
# 6. Запрос с невалидным X-API-Key — 401
# 7. Запрос без Idempotency-Key — 422
# 8. Невалидная валюта — 422
# 9. Отрицательная сумма — 422
# 10. Нулевая сумма — 422

API_KEY = "secret-api-key"
BASE_HEADERS = {"X-API-Key": API_KEY}

PAYMENT_BODY = {
    "amount": 100.50,
    "currency": "RUB",
    "description": "Test payment",
    "metadata": {"order_id": "123"},
    "webhook_url": "https://example.com/webhook",
}


def _headers(idempotency_key: str) -> dict:
    return {**BASE_HEADERS, "Idempotency-Key": idempotency_key}


@pytest.mark.asyncio
async def test_case_1(client: AsyncClient) -> None:
    """Успешное создание платежа — 202 Accepted."""
    response = await client.post(
        "/api/v1/payments",
        json=PAYMENT_BODY,
        headers=_headers(str(uuid.uuid4())),
    )

    assert response.status_code == HTTPStatus.ACCEPTED, response.text
    data = response.json()
    assert "payment_id" in data
    assert data["status"] == "pending"
    assert "created_at" in data


@pytest.mark.asyncio
async def test_case_2(client: AsyncClient, db_session: AsyncSession) -> None:
    """Платеж сохраняется в БД с корректными полями."""
    key = str(uuid.uuid4())
    response = await client.post(
        "/api/v1/payments",
        json=PAYMENT_BODY,
        headers=_headers(key),
    )
    data = response.json()

    result = await db_session.execute(
        select(PaymentRow).where(PaymentRow.id == data["payment_id"])
    )
    payment = result.scalar_one()

    assert payment.amount == Decimal("100.50")
    assert payment.currency == "RUB"
    assert payment.description == "Test payment"
    assert payment.metadata_ == {"order_id": "123"}
    assert payment.status == "pending"
    assert payment.idempotency_key == key


@pytest.mark.asyncio
async def test_case_3(client: AsyncClient, db_session: AsyncSession) -> None:
    """При создании платежа создается outbox-сообщение."""
    response = await client.post(
        "/api/v1/payments",
        json=PAYMENT_BODY,
        headers=_headers(str(uuid.uuid4())),
    )
    payment_id = response.json()["payment_id"]

    result = await db_session.execute(select(OutboxRow))
    messages = result.scalars().all()

    matching = [m for m in messages if m.payload.get("payment_id") == payment_id]
    assert len(matching) == 1
    assert matching[0].published is False
    assert matching[0].payload["retry_count"] == 0


@pytest.mark.asyncio
async def test_case_4(client: AsyncClient) -> None:
    """Повторный запрос с тем же Idempotency-Key возвращает тот же платеж."""
    key = str(uuid.uuid4())
    headers = _headers(key)

    resp1 = await client.post("/api/v1/payments", json=PAYMENT_BODY, headers=headers)
    resp2 = await client.post("/api/v1/payments", json=PAYMENT_BODY, headers=headers)

    assert resp1.status_code == HTTPStatus.ACCEPTED, resp1.text
    assert resp2.status_code == HTTPStatus.ACCEPTED, resp2.text
    assert resp1.json()["payment_id"] == resp2.json()["payment_id"]


@pytest.mark.asyncio
async def test_case_5(client: AsyncClient) -> None:
    """Запрос без X-API-Key — 422."""
    response = await client.post(
        "/api/v1/payments",
        json=PAYMENT_BODY,
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text


@pytest.mark.asyncio
async def test_case_6(client: AsyncClient) -> None:
    """Запрос с невалидным X-API-Key — 401."""
    response = await client.post(
        "/api/v1/payments",
        json=PAYMENT_BODY,
        headers={"X-API-Key": "wrong-key", "Idempotency-Key": str(uuid.uuid4())},
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED, response.text


@pytest.mark.asyncio
async def test_case_7(client: AsyncClient) -> None:
    """Запрос без Idempotency-Key — 422."""
    response = await client.post(
        "/api/v1/payments",
        json=PAYMENT_BODY,
        headers=BASE_HEADERS,
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "body_override",
    [
        pytest.param({"currency": "GBP"}, id="invalid_currency"),
        pytest.param({"amount": -10}, id="negative_amount"),
        pytest.param({"amount": 0}, id="zero_amount"),
    ],
)
async def test_case_8(client: AsyncClient, body_override: dict) -> None:
    """Невалидные данные в body — 422."""
    body = {**PAYMENT_BODY, **body_override}
    response = await client.post(
        "/api/v1/payments",
        json=body,
        headers=_headers(str(uuid.uuid4())),
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text
