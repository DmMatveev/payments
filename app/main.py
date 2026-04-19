import asyncio
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.entrypoints.http.dependencies import session
from app.entrypoints.http.exception_handlers import register_exception_handlers
from app.entrypoints.http.v1 import router as api_v1_router
from app.infrastructure.outbox_worker import outbox_worker



@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(outbox_worker())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Payment Processing Service", lifespan=lifespan)
register_exception_handlers(app)
app.include_router(api_v1_router)


