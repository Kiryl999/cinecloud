"""Probes for the container orchestrator.

Liveness says the process can still answer and checks no dependency on
purpose: if PostgreSQL is down, restarting every pod brings it no closer and
only adds a restart storm to the outage.

Readiness checks PostgreSQL, without which almost no route works; a pod that
fails it stops receiving traffic but keeps running. Redis is left out on
purpose: without it the seat map still works and only reserving fails, and
every other pod would be facing the same Redis anyway.
"""

import asyncio
import logging

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.deps import DbSession

logger = logging.getLogger("cinecloud.health")

router = APIRouter(prefix="/health", tags=["health"])

# well below the probe's own timeout, so a hanging database reads as "not
# ready" instead of as a probe that never answered
READINESS_TIMEOUT_SECONDS = 2.0


@router.get("/live")
async def live():
    return {"status": "ok"}


@router.get("/ready")
async def ready(db: DbSession):
    try:
        await asyncio.wait_for(db.execute(text("SELECT 1")), READINESS_TIMEOUT_SECONDS)
    except Exception as error:  # any failure means "not ready", whatever its type
        logger.warning("readiness check failed: %r", error)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unavailable"},
        )
    return {"status": "ok"}
