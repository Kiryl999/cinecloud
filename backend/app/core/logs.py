"""Log output and the access log.

In the cluster, logs go to stdout and a collector such as Loki or CloudWatch
picks them up. As JSON every line carries its fields - level, logger, route,
status, request id - so it can be filtered by field instead of searched as
text. In a terminal plain text reads better, so the format is a setting.

uvicorn's own loggers are routed through the same handler, and uvicorn's
access log is replaced by RequestLogMiddleware: one line per request with the
route template, status and duration as separate fields, which uvicorn's
preformatted access line does not offer.
"""

import json
import logging
import logging.config
import re
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

TEXT_FORMAT = "%(levelname)s:     %(name)s - %(message)s"

# Set by RequestLogMiddleware for the duration of one request. Every log
# record created meanwhile - in an endpoint, a service, a background task -
# picks it up, so all lines of one request can be found together.
request_id: ContextVar[str | None] = ContextVar("request_id", default=None)

# Attributes every LogRecord has; anything beyond them came in through `extra`
# or from the record factory below. Built from LogRecord itself, not through
# the factory, so request_id is not mistaken for a built-in.
_RECORD_ATTRIBUTES = set(vars(logging.LogRecord("", 0, "", 0, "", (), None))) | {
    "message",
    "asctime",
    # uvicorn's copy of the message with terminal colour codes
    "color_message",
}

_base_record_factory = logging.getLogRecordFactory()


def _record_with_request_id(*args, **kwargs) -> logging.LogRecord:
    record = _base_record_factory(*args, **kwargs)
    record.request_id = request_id.get()
    return record


class JsonFormatter(logging.Formatter):
    """One JSON object per line; fields passed via `extra` become keys."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "time": datetime.fromtimestamp(record.created, timezone.utc).isoformat(
                timespec="milliseconds"
            ),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        entry.update(
            (key, value)
            for key, value in vars(record).items()
            if key not in _RECORD_ATTRIBUTES and value is not None
        )
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            entry["stack"] = self.formatStack(record.stack_info)
        return json.dumps(entry, default=str, ensure_ascii=False)


def configure_logging(level: str, fmt: str) -> None:
    logging.setLogRecordFactory(_record_with_request_id)
    logging.config.dictConfig(
        {
            "version": 1,
            # loggers created at import time, like cinecloud.booking, keep working
            "disable_existing_loggers": False,
            "formatters": {
                "text": {"format": TEXT_FORMAT},
                "json": {"()": JsonFormatter},
            },
            "handlers": {
                "stdout": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                    "formatter": fmt,
                },
            },
            "root": {"level": level, "handlers": ["stdout"]},
            "loggers": {
                # startup and error messages of uvicorn, in the same format
                "uvicorn": {"level": level, "handlers": [], "propagate": True},
                "uvicorn.error": {"level": level, "handlers": [], "propagate": True},
                # replaced by RequestLogMiddleware
                "uvicorn.access": {"level": "WARNING", "handlers": [], "propagate": False},
            },
        }
    )


# A request id from outside ends up in every log line of the request, so only
# a harmless one is taken over; anything else gets replaced.
_VALID_REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{1,128}")

# probes every few seconds and Prometheus scrapes would drown the real traffic
_QUIET_PATHS = ("/health/", "/metrics")

access_logger = logging.getLogger("cinecloud.access")


class RequestLogMiddleware:
    """Gives every request an id and writes one access log line for it.

    The id comes from an incoming X-Request-ID header - the ingress can set
    one - or is generated, and is sent back in the response.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = Headers(scope=scope).get("x-request-id", "")
        rid = incoming if _VALID_REQUEST_ID.fullmatch(incoming) else uuid.uuid4().hex
        token = request_id.set(rid)
        started = time.perf_counter()
        status = 500  # what the client gets if the app raises before responding

        async def send_with_id(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                MutableHeaders(scope=message).append("X-Request-ID", rid)
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            path = scope["path"]
            if not path.startswith(_QUIET_PATHS):
                duration_ms = round((time.perf_counter() - started) * 1000, 1)
                access_logger.info(
                    "%s %s %d %.1fms",
                    scope["method"],
                    path,
                    status,
                    duration_ms,
                    extra={
                        "method": scope["method"],
                        "path": path,
                        # the template, e.g. /cinemas/{slug} - None if nothing matched
                        "route": getattr(scope.get("route"), "path", None),
                        "status": status,
                        "duration_ms": duration_ms,
                    },
                )
            request_id.reset(token)
