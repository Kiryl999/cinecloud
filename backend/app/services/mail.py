"""Outgoing e-mail: the confirmation a guest gets after booking.

Sent over SMTP to whatever server SMTP_HOST names - Mailpit on minikube,
which catches every message and shows it in a web UI, or a relay such as
Amazon SES wherever mail is meant to arrive. Without SMTP_HOST the
confirmation is only logged, which is what the tests and a bare `uvicorn` on
a laptop get.

It runs as a background task once the response is out (see api/booking.py),
in a worker thread: smtplib blocks, and the guest should not wait for a mail
server. A failed delivery is logged and counted but not retried - the
booking stands either way, and the reference is on the confirmation page.
"""

import logging
import smtplib
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from email.message import EmailMessage
from email.utils import formatdate, make_msgid, parseaddr
from itertools import groupby
from zoneinfo import ZoneInfo

from app.core import metrics
from app.core.config import settings

logger = logging.getLogger("cinecloud.mail")

# All cinemas on the platform are in Germany, so a showtime is given in their
# local time, as on the visitor pages (see frontend/src/utils/format.js).
CINEMA_TIME_ZONE = ZoneInfo("Europe/Berlin")

SMTP_TIMEOUT_SECONDS = 10


@dataclass(frozen=True)
class BookingConfirmation:
    """Everything the mail says, as plain values: the task runs after the
    request, when its database session is closed."""

    to: str
    reference: str
    cinema: str
    movie: str
    hall: str
    starts_at: datetime
    seats: list[tuple[int, int]]  # (row, seat number)
    total: Decimal


def _mask(address: str) -> str:
    # keeps logs useful for tracing without spreading full addresses around
    local, _, domain = address.partition("@")
    return f"{local[:1]}***@{domain}"


def _seat_lines(seats: list[tuple[int, int]]) -> list[str]:
    """One line per row: "Row 4, seats 4, 5, 7"."""
    lines = []
    for row, in_row in groupby(sorted(seats), key=lambda seat: seat[0]):
        numbers = [str(number) for _, number in in_row]
        noun = "seat" if len(numbers) == 1 else "seats"
        lines.append(f"Row {row}, {noun} {', '.join(numbers)}")
    return lines


def compose(confirmation: BookingConfirmation) -> EmailMessage:
    starts = confirmation.starts_at.astimezone(CINEMA_TIME_ZONE)
    seats = "\n".join(_seat_lines(confirmation.seats))

    message = EmailMessage()
    message["From"] = settings.mail_from
    message["To"] = confirmation.to
    message["Subject"] = f"Your tickets for {confirmation.movie} ({confirmation.reference})"
    # what smtplib leaves out, and spam filters look for
    message["Date"] = formatdate(usegmt=True)
    message["Message-ID"] = make_msgid(domain=parseaddr(settings.mail_from)[1].partition("@")[2])
    message.set_content(
        f"Thank you for booking at {confirmation.cinema}.\n"
        "\n"
        f"{confirmation.movie}\n"
        f"{starts:%A, %d %B %Y, %H:%M}\n"
        f"{confirmation.hall}\n"
        "\n"
        f"{seats}\n"
        "\n"
        f"Total: €{confirmation.total:.2f}\n"
        f"Booking reference: {confirmation.reference}\n"
        "\n"
        "Show the booking reference at the entrance.\n"
    )
    return message


def send_booking_confirmation(confirmation: BookingConfirmation) -> None:
    if not settings.smtp_host:
        logger.info(
            "booking confirmation %s (%d seats) would be sent to %s",
            confirmation.reference,
            len(confirmation.seats),
            _mask(confirmation.to),
        )
        metrics.BOOKING_MAILS.labels("logged").inc()
        return

    try:
        with smtplib.SMTP(
            settings.smtp_host, settings.smtp_port, timeout=SMTP_TIMEOUT_SECONDS
        ) as smtp:
            if settings.smtp_starttls:
                smtp.starttls()
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(compose(confirmation))
    # SMTPException is an OSError, so this also covers a server that cannot
    # be reached at all
    except OSError:
        logger.warning(
            "booking confirmation %s could not be sent to %s",
            confirmation.reference,
            _mask(confirmation.to),
            exc_info=True,
        )
        metrics.BOOKING_MAILS.labels("failed").inc()
        return

    logger.info(
        "booking confirmation %s sent to %s", confirmation.reference, _mask(confirmation.to)
    )
    metrics.BOOKING_MAILS.labels("sent").inc()
