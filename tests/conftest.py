from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from infrastructure.configs import settings
from infrastructure.db.models import Base


@pytest.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(settings.database_url, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession]:
    async with test_engine.connect() as conn:
        async with conn.begin() as trans:
            session = AsyncSession(bind=conn, expire_on_commit=False)
            yield session
            await trans.rollback()
