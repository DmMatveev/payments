import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import tests.factories


@pytest.fixture(autouse=True)
async def _setup_factories(db_session: AsyncSession):
    tests.factories._current_session = db_session
    tests.factories.BaseFactory._current_session = db_session
    yield
    tests.factories._current_session = None
    tests.factories.BaseFactory._current_session = None
