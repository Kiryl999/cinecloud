# syntax=docker/dockerfile:1

# One image for every backend role, each started with its own command:
#   API (default)      docker run <image>
#   migrations         docker run <image> alembic upgrade head
#   operator scripts   docker run <image> python -m scripts.seed_demo --slug ...
# Settings come from environment variables only, see app/core/config.py.

FROM python:3.12-slim AS build

COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /bin/uv

# bytecode is compiled once here instead of on every container start; uv must
# use the interpreter of the base image, the only one the runtime stage has
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# dependencies before the code: this layer is rebuilt only when uv.lock
# changes, not on every code change
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-dev --no-install-project


FROM python:3.12-slim

# unbuffered, so log lines reach the collector as they are written
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

# numeric ids, so Kubernetes can enforce runAsNonRoot without resolving a name
RUN groupadd --system --gid 10001 cinecloud \
 && useradd --system --uid 10001 --gid cinecloud --no-create-home cinecloud

WORKDIR /app

# owned by root and only readable for the app user: a compromised process
# cannot rewrite its own code
COPY --from=build /app/.venv ./.venv
COPY alembic.ini ./
COPY alembic ./alembic
COPY scripts ./scripts
COPY app ./app

USER 10001:10001

EXPOSE 8000

# Exec form, so uvicorn is PID 1 and receives SIGTERM itself. Open seat-map
# streams never end on their own: without the timeout uvicorn would wait for
# them until the pod is killed, and the cleanup in main.py's lifespan would
# never run. Browsers reconnect to another pod by themselves.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-graceful-shutdown", "10"]
