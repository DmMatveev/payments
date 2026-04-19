from collections.abc import AsyncGenerator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

import tests.factories
from app.entrypoints.http.dependencies import get_session
from app.entrypoints.http.exception_handlers import register_exception_handlers
from app.entrypoints.http.v1 import router


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


@pytest.fixture(autouse=True)
async def _setup_factories(db_session: AsyncSession):
    tests.factories._current_session = db_session
    tests.factories.BaseFactory._current_session = db_session
    yield
    tests.factories._current_session = None
    tests.factories.BaseFactory._current_session = None
