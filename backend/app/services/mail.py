"""Outgoing e-mail.

For now delivery is a log line. Real sending needs a mail service - an SMTP
relay or Amazon SES - which is an infrastructure decision; this function is
the only place the booking flow touches when that decision is made.
"""

import logging

logger = logging.getLogger("cinecloud.mail")


def _mask(address: str) -> str:
    # keeps logs useful for tracing without spreading full addresses around
    local, _, domain = address.partition("@")
    return f"{local[:1]}***@{domain}"


def send_booking_confirmation(*, to: str, reference: str, seat_count: int) -> None:
    logger.info(
        "booking confirmation %s (%d seats) would be sent to %s",
        reference,
        seat_count,
        _mask(to),
    )
