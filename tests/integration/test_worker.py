import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from entrypoints.messaging import worker
from entrypoints.messaging.worker import payments_queue, process_payment
from tests.factories import PaymentFactory

# Тест-кейсы:
# 1. Успешный платёж: статус succeeded, webhook отправлен, msg.ack
# 2. Нефинальный fail: статус остаётся pending, публикация в очередь с retry_count+1, msg.ack
# 3. Финальный fail: статус failed, webhook со статусом failed, msg.reject(requeue=False)
# 4. Редоставка уже succeeded платежа: шлюз не дёргается, webhook уходит повторно, msg.ack
# 5. Несуществующий платёж: msg.ack без падений


@pytest.fixture
def mock_msg() -> AsyncMock:
    msg = AsyncMock()
    msg.ack = AsyncMock()
    msg.reject = AsyncMock()
    return msg


@pytest.fixture
def mock_notify():
    with patch.object(worker.notifier, "notify", new=AsyncMock()) as m:
        yield m


@pytest.fixture
def mock_publish():
    with patch.object(worker.broker, "publish", new=AsyncMock()) as m:
        yield m


@pytest.fixture(autouse=True)
def _patch_sleep():
    with patch("asyncio.sleep", new=AsyncMock()):
        yield


def get_body(payment_id: uuid.UUID, retry_count: int = 0) -> dict:
    return {"payment_id": str(payment_id), "retry_count": retry_count}


@pytest.mark.asyncio
async def test_case_1(
    db_session: AsyncSession,
    mock_msg: AsyncMock,
    mock_notify: AsyncMock,
) -> None:
    """1. Успешный платёж: статус succeeded, webhook отправлен, msg.ack."""

    payment = await PaymentFactory.create()

    with patch("random.random", return_value=0.0):  # gateway success
        await process_payment(get_body(payment.id), mock_msg)

    await db_session.refresh(payment)
    assert payment.status == "succeeded"
    assert payment.processed_at is not None

    mock_notify.assert_awaited_once()
    url, payload = mock_notify.call_args.args
    assert url == payment.webhook_url
    assert payload["status"] == "succeeded"
    assert payload["payment_id"] == str(payment.id)

    mock_msg.ack.assert_awaited_once()
    mock_msg.reject.assert_not_awaited()


@pytest.mark.asyncio
async def test_case_2(
    db_session: AsyncSession,
    mock_msg: AsyncMock,
    mock_notify: AsyncMock,
    mock_publish: AsyncMock,
) -> None:
    """2. Нефинальный fail: pending, publish в очередь с retry_count+1, msg.ack."""

    payment = await PaymentFactory.create()

    with patch("random.random", return_value=1.0):  # gateway fail
        await process_payment(get_body(payment.id, retry_count=0), mock_msg)

    await db_session.refresh(payment)
    assert payment.status == "pending"
    assert payment.processed_at is None

    mock_notify.assert_not_awaited()
    mock_publish.assert_awaited_once()
    published_body = mock_publish.call_args.args[0]
    assert published_body["retry_count"] == 1
    assert published_body["payment_id"] == str(payment.id)
    assert mock_publish.call_args.kwargs["queue"] is payments_queue

    mock_msg.ack.assert_awaited_once()
    mock_msg.reject.assert_not_awaited()


@pytest.mark.asyncio
async def test_case_3(
    db_session: AsyncSession,
    mock_msg: AsyncMock,
    mock_notify: AsyncMock,
    mock_publish: AsyncMock,
) -> None:
    """3. Финальный fail: status=failed, webhook(failed), msg.reject(requeue=False)."""

    payment = await PaymentFactory.create()

    with patch("random.random", return_value=1.0):  # gateway fail
        await process_payment(
            get_body(payment.id, retry_count=worker.MAX_RETRIES - 1), mock_msg
        )

    await db_session.refresh(payment)
    assert payment.status == "failed"
    assert payment.processed_at is not None

    mock_notify.assert_awaited_once()
    _, payload = mock_notify.call_args.args
    assert payload["status"] == "failed"
    assert payload["payment_id"] == str(payment.id)

    mock_publish.assert_not_awaited()
    mock_msg.reject.assert_awaited_once_with(requeue=False)
    mock_msg.ack.assert_not_awaited()


@pytest.mark.asyncio
async def test_case_4(
    mock_msg: AsyncMock,
    mock_notify: AsyncMock,
) -> None:
    """4. Редоставка уже succeeded платежа: шлюз не дёргается, webhook уходит, msg.ack."""

    payment = await PaymentFactory.create(status="succeeded")

    random_calls = 0

    def counting_random():
        nonlocal random_calls
        random_calls += 1
        return 0.0

    with patch("random.random", side_effect=counting_random):
        await process_payment(get_body(payment.id), mock_msg)

    assert random_calls == 0, "gateway must be skipped for already-succeeded payment"

    mock_notify.assert_awaited_once()
    _, payload = mock_notify.call_args.args
    assert payload["status"] == "succeeded"

    mock_msg.ack.assert_awaited_once()


@pytest.mark.asyncio
async def test_case_5(
    mock_msg: AsyncMock,
    mock_notify: AsyncMock,
    mock_publish: AsyncMock,
) -> None:
    """5. Несуществующий платёж: msg.ack, без падений и сайд-эффектов."""

    await process_payment(get_body(uuid.uuid4()), mock_msg)

    mock_notify.assert_not_awaited()
    mock_publish.assert_not_awaited()
    mock_msg.ack.assert_awaited_once()
    mock_msg.reject.assert_not_awaited()
