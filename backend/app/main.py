from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
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
from app.core.logs import RequestLogMiddleware, configure_logging
from app.core.redis import redis_client

# replaces uvicorn's logging setup, which covers only its own loggers, with
# one that also shows the application's (e.g. cinecloud.booking)
configure_logging(settings.log_level, settings.log_format)


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    # a pod being replaced closes its connections instead of leaving them to
    # time out on the servers
    await redis_client.aclose()
    await engine.dispose()


app = FastAPI(
    title="CineCloud API",
    lifespan=lifespan,
    # "Authorize" in /docs signs in as the frontend does: the realm's public
    # client, with PKCE instead of a client secret
    swagger_ui_init_oauth={
        "clientId": "cinecloud-web",
        "usePkceWithAuthorizationCodeGrant": True,
    },
)

app.add_middleware(RequestLogMiddleware)


@app.exception_handler(RedisError)
async def redis_unavailable(_: Request, __: RedisError) -> JSONResponse:
    # Seat holds live in Redis, so without it nobody can reserve. That is an
    # outage of a dependency, not a bug: 503 tells clients to try again later.
    metrics.REDIS_FAILURES.labels("request").inc()
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "Booking is temporarily unavailable"},
    )


# Every public router carries /api in its own prefix. The ingress routes only
# that path, which keeps /health, /metrics and /docs inside the cluster and
# keeps API paths apart from frontend routes such as /cinemas/:slug. A prefix
# added here instead would be missing from the route in the access log.
app.include_router(auth_router)
app.include_router(cinemas_router)
app.include_router(booking_router)
app.include_router(halls_router)
app.include_router(health_router)
app.include_router(movies_router)
app.include_router(showtimes_router)

metrics.instrument(app)
