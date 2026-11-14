"""Booking confirmations: what the mail says, and how it gets out - or why it
does not.

The SMTP connection is a stand-in that records what it is asked to do. What
reaches a real server is checked by hand against Mailpit (k8s/README.md).
"""

import logging
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from smtplib import SMTPRecipientsRefused

import pytest
from prometheus_client import REGISTRY

from app.core.config import settings
from app.services import mail

CONFIRMATION = mail.BookingConfirmation(
    to="anna@kino-alpha.de",
    reference="DYFGRBG3",
    cinema="Kino Alpha",
    movie="Dune: Part Two",
    hall="Saal 1",
    # 16:00 in Berlin, which is on winter time in November
    starts_at=datetime(2026, 11, 14, 15, 0, tzinfo=timezone.utc),
    seats=[(4, 7), (2, 11), (4, 4)],
    total=Decimal("37.50"),
)


def _mails(outcome: str) -> float:
    # counters keep counting across tests, so compare before and after
    return REGISTRY.get_sample_value("cinecloud_booking_mails_total", {"outcome": outcome}) or 0.0


@pytest.fixture
def smtp(monkeypatch):
    """A mail server at mail.test:1025; returns the connections made to it."""
    connections = []

    class RecordingSMTP:
        def __init__(self, host, port, timeout):
            self.address = (host, port)
            self.timeout = timeout
            self.steps = []
            self.sent = []
            connections.append(self)

        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            self.steps.append("quit")

        def starttls(self):
            self.steps.append("starttls")

        def login(self, user, password):
            self.steps.append(("login", user, password))

        def send_message(self, message):
            self.steps.append("send")
            self.sent.append(message)

    monkeypatch.setattr(mail.smtplib, "SMTP", RecordingSMTP)
    monkeypatch.setattr(settings, "smtp_host", "mail.test")
    monkeypatch.setattr(settings, "smtp_port", 1025)
    return connections


def test_without_a_mail_server_the_confirmation_is_only_logged(monkeypatch, caplog):
    monkeypatch.setattr(settings, "smtp_host", "")

    def no_connection(*args, **kwargs):
        raise AssertionError("no mail server is configured")

    monkeypatch.setattr(mail.smtplib, "SMTP", no_connection)
    before = _mails("logged")

    with caplog.at_level(logging.INFO, logger="cinecloud.mail"):
        mail.send_booking_confirmation(CONFIRMATION)

    assert "DYFGRBG3 (3 seats) would be sent to a***@kino-alpha.de" in caplog.text
    assert _mails("logged") == before + 1


def test_the_confirmation_goes_out_over_smtp(smtp, caplog):
    before = _mails("sent")

    with caplog.at_level(logging.INFO, logger="cinecloud.mail"):
        mail.send_booking_confirmation(CONFIRMATION)

    [connection] = smtp
    assert connection.address == ("mail.test", 1025)
    assert connection.timeout == mail.SMTP_TIMEOUT_SECONDS
    # Mailpit wants neither TLS nor a login
    assert connection.steps == ["send", "quit"]

    [message] = connection.sent
    assert message["To"] == "anna@kino-alpha.de"
    assert message["From"] == settings.mail_from
    assert message["Subject"] == "Your tickets for Dune: Part Two (DYFGRBG3)"
    assert message["Date"] and message["Message-ID"]

    assert _mails("sent") == before + 1
    # the full address stays out of the logs here as well
    assert "anna@kino-alpha.de" not in caplog.text


def test_the_mail_gives_the_showtime_in_the_cinemas_time_and_the_seats_by_row():
    body = mail.compose(CONFIRMATION).get_content()

    assert "Thank you for booking at Kino Alpha." in body
    assert "Dune: Part Two\nSaturday, 14 November 2026, 16:00\nSaal 1\n" in body
    assert "Row 2, seat 11\nRow 4, seats 4, 7\n" in body
    assert "Total: €37.50" in body
    assert "Booking reference: DYFGRBG3" in body


def test_summer_time_is_taken_into_account():
    # 18:00 UTC in July is 20:00 in Berlin, two hours ahead rather than one
    summer = replace(CONFIRMATION, starts_at=datetime(2026, 7, 1, 18, 0, tzinfo=timezone.utc))

    assert "Wednesday, 01 July 2026, 20:00" in mail.compose(summer).get_content()


def test_a_relay_on_the_internet_gets_tls_before_the_credentials(smtp, monkeypatch):
    monkeypatch.setattr(settings, "smtp_starttls", True)
    monkeypatch.setattr(settings, "smtp_username", "AKIA-EXAMPLE")
    monkeypatch.setattr(settings, "smtp_password", "secret")

    mail.send_booking_confirmation(CONFIRMATION)

    [connection] = smtp
    assert connection.steps == ["starttls", ("login", "AKIA-EXAMPLE", "secret"), "send", "quit"]


class _UnreachableSMTP:
    def __init__(self, *args, **kwargs):
        raise ConnectionRefusedError()


class _RefusingSMTP:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        pass

    def send_message(self, message):
        raise SMTPRecipientsRefused({"anna@kino-alpha.de": (550, b"no such user")})


@pytest.mark.parametrize(
    "server", [_UnreachableSMTP, _RefusingSMTP], ids=["unreachable", "recipient refused"]
)
def test_a_failed_delivery_is_logged_and_counted_but_not_raised(monkeypatch, caplog, server):
    monkeypatch.setattr(settings, "smtp_host", "mail.test")
    monkeypatch.setattr(mail.smtplib, "SMTP", server)
    before = _mails("failed")

    with caplog.at_level(logging.WARNING, logger="cinecloud.mail"):
        mail.send_booking_confirmation(CONFIRMATION)

    assert "DYFGRBG3 could not be sent to a***@kino-alpha.de" in caplog.text
    assert _mails("failed") == before + 1
