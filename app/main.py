import asyncio
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from entrypoints.http.dependencies import get_session
from entrypoints.http.exception_handlers import register_exception_handlers
from entrypoints.http.v1 import router as api_v1_router
from infrastructure.outbox_relay import run_outbox_relay



@asynccontextmanager
async def lifespan(_: FastAPI):
    task = asyncio.create_task(run_outbox_relay())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Payment Processing Service", lifespan=lifespan)
register_exception_handlers(app)
app.include_router(api_v1_router)


