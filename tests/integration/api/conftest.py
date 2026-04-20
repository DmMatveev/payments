from collections.abc import AsyncGenerator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from entrypoints.http.dependencies import get_session
from entrypoints.http.exception_handlers import register_exception_handlers
from entrypoints.http.v1 import router


@pytest.fixture
def app(db_session: AsyncSession) -> FastAPI:
    app_instance = FastAPI()
    register_exception_handlers(app_instance)
    app_instance.include_router(router)

    async def override_session() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app_instance.dependency_overrides[get_session] = override_session
    return app_instance


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c
