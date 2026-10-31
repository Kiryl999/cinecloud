"""JSON log lines, request ids and the access log."""

import json
import logging
import sys

from app.core import logs
from app.main import app  # noqa: F401  -- configures logging, as in production
from tests.test_booking import _showtime


def _record(msg: str, *args, exc_info=None, **extra) -> logging.LogRecord:
    """A record created the way logger calls create them, extras included."""
    return logging.getLogger("cinecloud.test").makeRecord(
        "cinecloud.test", logging.WARNING, __file__, 1, msg, args, exc_info, extra=extra
    )


def _access_records(caplog) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.name == "cinecloud.access"]


# --- the formatter ------------------------------------------------------------


def test_a_json_line_carries_the_message_and_extra_fields():
    line = logs.JsonFormatter().format(_record("seat %s held", 7, route="/x", status=201))

    entry = json.loads(line)
    assert entry["level"] == "WARNING"
    assert entry["logger"] == "cinecloud.test"
    assert entry["message"] == "seat 7 held"
    assert entry["route"] == "/x"
    assert entry["status"] == 201
    assert entry["time"].endswith("+00:00")


def test_a_json_line_leaves_out_empty_fields():
    entry = json.loads(logs.JsonFormatter().format(_record("outside a request", route=None)))

    assert "route" not in entry
    assert "request_id" not in entry


def test_a_json_line_includes_the_request_id_while_one_is_set():
    token = logs.request_id.set("abc123")
    try:
        record = _record("inside a request")
    finally:
        logs.request_id.reset(token)

    assert json.loads(logs.JsonFormatter().format(record))["request_id"] == "abc123"


def test_a_json_line_keeps_the_traceback_in_one_field():
    try:
        raise ValueError("boom")
    except ValueError:
        record = _record("failed", exc_info=sys.exc_info())

    line = logs.JsonFormatter().format(record)

    assert "\n" not in line  # one event, one line - a collector must not split it
    assert "ValueError: boom" in json.loads(line)["exception"]


# --- request ids --------------------------------------------------------------


async def test_every_response_carries_a_request_id(client):
    response = await client.get("/cinemas/")

    assert len(response.headers["x-request-id"]) == 32


async def test_a_request_id_from_the_ingress_is_kept(client):
    response = await client.get("/cinemas/", headers={"X-Request-ID": "ingress-42.a_b"})

    assert response.headers["x-request-id"] == "ingress-42.a_b"


async def test_a_request_id_that_could_garble_the_logs_is_replaced(client):
    for unsafe in ("<script>alert(1)</script>", "x" * 129, "two words"):
        response = await client.get("/cinemas/", headers={"X-Request-ID": unsafe})

        assert response.headers["x-request-id"] != unsafe


async def test_log_lines_written_during_a_request_carry_its_id(client, tenant_a, caplog):
    url, _, (s1, *_) = await _showtime(client, tenant_a)
    token = (await client.post(f"{url}/holds", json={"seat_ids": [s1]})).json()["hold_token"]
    caplog.set_level(logging.INFO)

    response = await client.post(
        f"{url}/bookings", json={"hold_token": token, "guest_email": "anna@kino-alpha.de"}
    )

    # the confirmation mail runs as a background task after the response
    (mail,) = [r for r in caplog.records if r.name == "cinecloud.mail"]
    assert mail.request_id == response.headers["x-request-id"]


# --- the access log -----------------------------------------------------------


async def test_one_access_line_per_request_with_route_and_status(client, caplog):
    caplog.set_level(logging.INFO)

    response = await client.get("/cinemas/no-such-cinema")

    (line,) = _access_records(caplog)
    assert line.method == "GET"
    assert line.path == "/api/cinemas/no-such-cinema"
    assert line.route == "/api/cinemas/{slug}"
    assert line.status == 404
    assert line.duration_ms >= 0
    assert line.request_id == response.headers["x-request-id"]


async def test_probes_and_scrapes_stay_out_of_the_access_log(internal_client, caplog):
    caplog.set_level(logging.INFO)

    await internal_client.get("/health/live")
    await internal_client.get("/metrics")

    assert _access_records(caplog) == []
