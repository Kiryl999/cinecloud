"""Prometheus metrics, exposed at /metrics.

HTTP metrics - requests and latency per route and status - come from the
instrumentator. The metrics below describe the booking flow itself, which is
what dashboards and alerts are really about: a spike in 409s is normal on a
premiere night, a rising count of Redis failures is not.

Values live in process memory. That is why a container runs a single uvicorn
worker: several workers would each report only their own share, and the
deployment scales by running more pods instead.

/metrics is meant for Prometheus inside the cluster and must not be routed
through the public ingress.
"""

from fastapi import FastAPI
from prometheus_client import Counter, Gauge
from prometheus_fastapi_instrumentator import Instrumentator

SEAT_HOLDS = Counter(
    "cinecloud_seat_holds",
    "Attempts to hold seats, by outcome",
    ["outcome"],  # placed | unavailable | invalid
)
BOOKINGS = Counter(
    "cinecloud_bookings",
    "Attempts to turn a hold into a booking, by outcome",
    ["outcome"],  # confirmed | expired | unavailable
)
SEATS_SOLD = Counter("cinecloud_seats_sold", "Seats sold")
SEAT_STREAMS = Gauge("cinecloud_seat_streams_open", "Live seat-map streams currently open")
REDIS_FAILURES = Counter(
    "cinecloud_redis_failures",
    "Redis operations that failed, by what it cost",
    # request:   a request failed with 503
    # seat_map:  a seat map went out without holds
    # release:   a sold hold stayed in Redis until its expiry
    ["context"],
)

# Every series exists from the start with 0. Otherwise a counter appears only
# on its first increment, and rate() and alerts have nothing to compare it to.
for _outcome in ("placed", "unavailable", "invalid"):
    SEAT_HOLDS.labels(_outcome)
for _outcome in ("confirmed", "expired", "unavailable"):
    BOOKINGS.labels(_outcome)
for _context in ("request", "seat_map", "release"):
    REDIS_FAILURES.labels(_context)


def instrument(app: FastAPI) -> None:
    Instrumentator(
        # 409 and 503 mean very different things here; "4xx" and "5xx" would
        # hide exactly the codes worth watching
        should_group_status_codes=False,
        # A seat stream stays open for minutes. Its latency is the time to the
        # first byte, not the lifetime of the connection.
        should_exclude_streaming_duration=True,
        # probes and scrapes would drown the real traffic
        excluded_handlers=["^/metrics$", "^/health/"],
    ).instrument(app).expose(app, include_in_schema=False)
