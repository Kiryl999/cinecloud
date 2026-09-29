"""Reusable validation building blocks for request schemas."""

from pydantic import BeforeValidator


def _reject_null(value):
    if value is None:
        raise ValueError("may be omitted, but must not be null")
    return value


# Marks a PATCH field as "may be left out, but not set to null".
#
# PATCH fields are Optional so that clients can omit them. For columns that are
# NOT NULL in the database, an explicit null would otherwise pass validation and
# only fail on commit - with a 500 instead of a 422. Omitted fields never reach
# a validator, so this fires on explicit nulls only.
NotNull = BeforeValidator(_reject_null)
