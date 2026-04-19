import uuid
from http import HTTPStatus

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models import PaymentRow
from tests.factories import PaymentFactory

# Тест-кейсы:
# 1. Получение платежа — возвращаются все поля
# 2. Платеж не найден — 404
# 3. Невалидный UUID — 422
# 4. Запрос без X-API-Key — 422

API_KEY = "secret-api-key"
HEADERS = {"X-API-Key": API_KEY}


async def get_payment_expected_result(session: AsyncSession, payment_id: uuid.UUID) -> dict:
    payment = await session.get(PaymentRow, payment_id)
    return {
        "id": str(payment.id),
        "amount": str(payment.amount),
        "currency": payment.currency,
        "description": payment.description,
        "metadata": payment.metadata_,
        "status": payment.status,
        "idempotency_key": payment.idempotency_key,
        "webhook_url": payment.webhook_url,
        "created_at": payment.created_at.isoformat(),
        "processed_at": payment.processed_at.isoformat() if payment.processed_at else None,
    }


@pytest.mark.asyncio
async def test_case_1(client: AsyncClient, db_session: AsyncSession) -> None:
    """Получение платежа — возвращаются все поля."""
    payment = await PaymentFactory.create(
        amount=250,
        currency="USD",
        description="Get test payment",
        metadata_={"ref": "abc"},
    )

    response = await client.get(
        f"/api/v1/payments/{payment.id}",
        headers=HEADERS,
    )

    assert response.status_code == HTTPStatus.OK, response.text
    expected = await get_payment_expected_result(db_session, payment.id)
    assert response.json() == expected


@pytest.mark.asyncio
async def test_case_2(client: AsyncClient) -> None:
    """Платеж не найден — 404."""
    response = await client.get(
        f"/api/v1/payments/{uuid.uuid4()}",
        headers=HEADERS,
    )
    assert response.status_code == HTTPStatus.NOT_FOUND, response.text


@pytest.mark.asyncio
async def test_case_3(client: AsyncClient) -> None:
    """Невалидный UUID — 422."""
    response = await client.get(
        "/api/v1/payments/not-a-uuid",
        headers=HEADERS,
    )
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text


@pytest.mark.asyncio
async def test_case_4(client: AsyncClient) -> None:
    """Запрос без X-API-Key — 422."""
    response = await client.get(f"/api/v1/payments/{uuid.uuid4()}")
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, response.text
