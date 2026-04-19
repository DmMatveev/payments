from collections.abc import AsyncGenerator

from fastapi import Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.configs.config import settings
from app.infrastructure.configs.session import async_session


async def verify_api_key(x_api_key: str = Header(...)) -> str:
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key


async def session() -> AsyncGenerator[AsyncSession]:
    async with async_session() as session:
        yield session
