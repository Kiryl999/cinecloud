import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.exceptions import RedisError

import app.models  # noqa: F401  -- registers all models with the SQLModel mapper
from app.api.auth import router as auth_router
from app.api.booking import router as booking_router
from app.api.cinemas import router as cinemas_router
from app.api.halls import router as halls_router
from app.api.health import router as health_router
from app.api.movies import router as movies_router
from app.api.showtimes import router as showtimes_router
from app.core import metrics
from app.core.config import settings
from app.core.database import engine
from app.core.redis import redis_client

# uvicorn configures only its own loggers; this makes the application's
# messages (e.g. cinecloud.booking, cinecloud.mail) visible as well
logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s - %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    # a pod being replaced closes its connections instead of leaving them to
    # time out on the servers
    await redis_client.aclose()
    await engine.dispose()


app = FastAPI(title="CineCloud API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RedisError)
async def redis_unavailable(_: Request, __: RedisError) -> JSONResponse:
    # Seat holds live in Redis, so without it nobody can reserve. That is an
    # outage of a dependency, not a bug: 503 tells clients to try again later.
    metrics.REDIS_FAILURES.labels("request").inc()
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "Booking is temporarily unavailable"},
    )


app.include_router(auth_router)
app.include_router(cinemas_router)
app.include_router(booking_router)
app.include_router(halls_router)
app.include_router(health_router)
app.include_router(movies_router)
app.include_router(showtimes_router)

metrics.instrument(app)
