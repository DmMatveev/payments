import uuid
from typing import Generic, TypeVar

import factory
import factory.fuzzy
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models import OutboxRow, PaymentRow

T = TypeVar("T")

_current_session: AsyncSession | None = None


class BaseFactory(factory.alchemy.SQLAlchemyModelFactory, Generic[T]):
    _current_session: AsyncSession | None = None

    class Meta:
        abstract = True
        sqlalchemy_session_persistence = "flush"

    @classmethod
    def _get_session(cls):
        if cls._current_session is None:
            raise RuntimeError("Factory session not set")
        return cls._current_session.sync_session

    @classmethod
    async def create(cls, **kwargs) -> T:
        session = cls._current_session
        if session is None:
            raise RuntimeError("Factory session not set")

        def _create(s):
            cls._meta.sqlalchemy_session = s
            return super(BaseFactory, cls).create(**kwargs)

        return await session.run_sync(lambda s: _create(s))

    @classmethod
    async def create_batch(cls, size: int, **kwargs) -> list[T]:
        return [await cls.create(**kwargs) for _ in range(size)]


class PaymentFactory(BaseFactory[PaymentRow]):
    class Meta:
        model = PaymentRow

    id = factory.LazyFunction(uuid.uuid4)
    amount = factory.Faker("pydecimal", left_digits=4, right_digits=2, positive=True)
    currency = factory.fuzzy.FuzzyChoice(["RUB", "USD", "EUR"])
    description = factory.Faker("sentence")
    metadata_ = factory.LazyFunction(lambda: {"order_id": str(uuid.uuid4())})
    status = "pending"
    idempotency_key = factory.LazyFunction(lambda: str(uuid.uuid4()))
    webhook_url = factory.Faker("url")


class OutboxMessageFactory(BaseFactory[OutboxRow]):
    class Meta:
        model = OutboxRow

    id = factory.LazyFunction(uuid.uuid4)
    payload = factory.LazyFunction(lambda: {"payment_id": str(uuid.uuid4()), "retry_count": 0})
    published = False
