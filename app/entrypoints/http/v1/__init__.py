from fastapi import APIRouter, Depends

from app.entrypoints.http.dependencies import verify_api_key
from app.entrypoints.http.v1.payments.endpoint import router as payments_router

router = APIRouter(prefix="/api/v1", dependencies=[Depends(verify_api_key)])
router.include_router(payments_router)
