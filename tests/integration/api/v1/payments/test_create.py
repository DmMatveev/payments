import uuid
from http import HTTPStatus

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.db.models import PaymentModel
from tests.factories import PaymentFactory

# Тест-кейсы:
# 1. Успешное создание платежа — 202 с пустым телом
# 2. Повторный запрос с тем же Idempotency-Key не создает дубликат
# 3. Запрос без X-API-Key — 422
# 4. Запрос с невалидным X-API-Key — 401
# 5. Запрос без Idempotency-Key — 422
# 6. Невалидная валюта / отрицательная / нулевая сумма — 422

API_KEY = "secret-api-key"
BASE_HEADERS = {"X-API-Key": API_KEY}

PAYMENT_BODY = {
    "amount": 100.50,
    "currency": "RUB",
    "description": "Test payment",
    "metadata": {"order_id": "123"},
    "webhook_url": "https://example.com/webhook",
}


def make_headers(key: str) -> dict:
    return {**BASE_HEADERS, "Idempotency-Key": key}


async def get_expected_result(session: AsyncSession, idempotency_key: str) -> dict:
    result = await session.execute(
        select(PaymentModel).where(PaymentModel.idempotency_key == idempotency_key)
    )
    payment = result.scalar_one()
    return {
        "payment_id": str(payment.id),
        "status": payment.status,
        "created_at": payment.created_at.isoformat(),
    }


@pytest.mark.asyncio
async def test_case_1(db_session: AsyncSession, client: AsyncClient) -> None:
    """1. Успешное создание платежа — 202 Accepted."""

    key = str(uuid.uuid4())

    response = await client.post(
        "/api/v1/payments",
        json=PAYMENT_BODY,
        headers=make_headers(key),
    )

    assert response.status_code == HTTPStatus.ACCEPTED, response.text
    assert response.json() == await get_expected_result(db_session, key)


@pytest.mark.asyncio
async def test_case_2(client: AsyncClient, db_session: AsyncSession) -> None:
    """2. Повторный запрос с тем же Idempotency-Key возвращает тот же платеж."""

    key = str(uuid.uuid4())
    await PaymentFactory.create(idempotency_key=key)

    response = await client.post(
        "/api/v1/payments",
        json=PAYMENT_BODY,
        headers=make_headers(key),
    )

    assert response.status_code == HTTPStatus.ACCEPTED, response.text
    assert response.json() == await get_expected_result(db_session, key)


@pytest.mark.asyncio
async def test_case_3(client: AsyncClient) -> None:
    """3. Запрос без X-API-Key — 422."""

    response = await client.post(
        "/api/v1/payments",
        json=PAYMENT_BODY,
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text


@pytest.mark.asyncio
async def test_case_4(client: AsyncClient) -> None:
    """4. Запрос с невалидным X-API-Key — 401."""

    response = await client.post(
        "/api/v1/payments",
        json=PAYMENT_BODY,
        headers={"X-API-Key": "wrong-key", "Idempotency-Key": str(uuid.uuid4())},
    )
    assert response.status_code == HTTPStatus.UNAUTHORIZED, response.text


@pytest.mark.asyncio
async def test_case_5(client: AsyncClient) -> None:
    """5. Запрос без Idempotency-Key — 422."""

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
async def test_case_6(client: AsyncClient, body_override: dict) -> None:
    """6. Невалидные данные в body — 422."""

    body = {**PAYMENT_BODY, **body_override}
    response = await client.post(
        "/api/v1/payments",
        json=body,
        headers=make_headers(str(uuid.uuid4())),
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text
