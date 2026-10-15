"""Temporary seat holds in Redis.

A hold reserves seats for one guest while they check out. Redis suits exactly
that: the hold is short-lived, expires on its own through a TTL, and the Lua
scripts below run atomically - Redis executes one script at a time, so two
guests can never both get the same seat.

Redis is deliberately *not* the record of what is sold. That lives in
PostgreSQL (booking_seats), which survives a restart. A hold lost in a Redis
failover costs a guest some convenience, never a double booking.

Key layout:

    hold:{42}:seat:7          -> token      one key per held seat
    hold:{42}:token:<token>   -> "7,8,9"    the seats a token holds

The {42} part is a Redis Cluster hash tag: all keys of one showtime land in the
same slot, so the multi-key scripts stay valid on a clustered deployment.
"""

import json
import math
import secrets
from dataclasses import dataclass

from redis.asyncio import Redis

HOLD_SECONDS = 10 * 60

# Long enough to take the payment and commit the sale, deliberately no longer:
# securing a hold must not become a way to keep seats indefinitely.
CONFIRM_SECONDS = 60

# All or nothing: if any seat is held, nothing is held. The event is published
# only on success - a failed attempt changes nothing anyone needs to hear about.
#   KEYS: seat keys..., token key    ARGV: token, ttl ms, seat list, channel, event
_PLACE = """
for i = 1, #KEYS - 1 do
    if redis.call('EXISTS', KEYS[i]) == 1 then
        return 0
    end
end
for i = 1, #KEYS - 1 do
    redis.call('SET', KEYS[i], ARGV[1], 'PX', ARGV[2])
end
redis.call('SET', KEYS[#KEYS], ARGV[3], 'PX', ARGV[2])
redis.call('PUBLISH', ARGV[4], ARGV[5])
return 1
"""

# The token must still own every one of its seats. Their lifetime is raised to
# at least the confirm window, but never extended beyond it.
#   KEYS: token key, seat keys...    ARGV: token, min ttl ms, seat list
_SECURE = """
if redis.call('GET', KEYS[1]) ~= ARGV[3] then
    return 0
end
for i = 2, #KEYS do
    if redis.call('GET', KEYS[i]) ~= ARGV[1] then
        return 0
    end
end
for i = 1, #KEYS do
    if redis.call('PTTL', KEYS[i]) < tonumber(ARGV[2]) then
        redis.call('PEXPIRE', KEYS[i], ARGV[2])
    end
end
return 1
"""

# After the sale is committed: drop the hold and announce the sale. Only keys
# that still carry this token are deleted.
#   KEYS: token key, seat keys...    ARGV: token, channel, event
_RELEASE = """
for i = 2, #KEYS do
    if redis.call('GET', KEYS[i]) == ARGV[1] then
        redis.call('DEL', KEYS[i])
    end
end
redis.call('DEL', KEYS[1])
redis.call('PUBLISH', ARGV[2], ARGV[3])
return 1
"""


@dataclass
class Hold:
    token: str
    seat_ids: list[int]
    expires_in: int  # seconds


def channel(showtime_id: int) -> str:
    """Pub/Sub channel announcing seat changes of one showtime."""
    return f"showtime:{showtime_id}:seats"


def _seat_key(showtime_id: int, seat_id: int) -> str:
    return f"hold:{{{showtime_id}}}:seat:{seat_id}"


def _token_key(showtime_id: int, token: str) -> str:
    return f"hold:{{{showtime_id}}}:token:{token}"


def _seat_list(seat_ids: list[int]) -> str:
    return ",".join(str(seat_id) for seat_id in seat_ids)


async def place(redis: Redis, showtime_id: int, seat_ids: list[int]) -> Hold | None:
    """Hold every seat in `seat_ids`, or none of them. None if any is taken."""
    # unguessable: whoever presents the token may book the held seats
    token = secrets.token_urlsafe(24)
    event = json.dumps({"event": "held", "seat_ids": seat_ids, "expires_in": HOLD_SECONDS})

    placed = await redis.register_script(_PLACE)(
        keys=[_seat_key(showtime_id, s) for s in seat_ids] + [_token_key(showtime_id, token)],
        args=[token, HOLD_SECONDS * 1000, _seat_list(seat_ids), channel(showtime_id), event],
    )
    return Hold(token, seat_ids, HOLD_SECONDS) if placed == 1 else None


async def secure(redis: Redis, showtime_id: int, token: str) -> list[int] | None:
    """Confirm the token still holds its seats and keep them for the checkout.

    Returns the held seat ids, or None if the hold expired or belongs to nobody.
    """
    seat_list = await redis.get(_token_key(showtime_id, token))
    if seat_list is None:
        return None
    seat_ids = [int(seat_id) for seat_id in seat_list.split(",")]

    secured = await redis.register_script(_SECURE)(
        keys=[_token_key(showtime_id, token)] + [_seat_key(showtime_id, s) for s in seat_ids],
        args=[token, CONFIRM_SECONDS * 1000, seat_list],
    )
    return seat_ids if secured == 1 else None


async def release(redis: Redis, showtime_id: int, token: str, seat_ids: list[int]) -> None:
    """Drop a hold whose seats were sold, and announce the sale."""
    event = json.dumps({"event": "booked", "seat_ids": seat_ids})
    await redis.register_script(_RELEASE)(
        keys=[_token_key(showtime_id, token)] + [_seat_key(showtime_id, s) for s in seat_ids],
        args=[token, channel(showtime_id), event],
    )


async def seconds_left(redis: Redis, showtime_id: int, seat_ids: list[int]) -> dict[int, int]:
    """Remaining hold time per held seat, in whole seconds; free seats are left out.

    Seconds rather than an expiry timestamp: the browser counts down from when
    it received the value, so a visitor's wrong system clock does not matter.
    """
    if not seat_ids:
        return {}
    async with redis.pipeline(transaction=False) as pipe:
        for seat_id in seat_ids:
            pipe.pttl(_seat_key(showtime_id, seat_id))
        remaining = await pipe.execute()
    # PTTL is -2 for a missing key
    return {
        seat_id: math.ceil(ms / 1000)
        for seat_id, ms in zip(seat_ids, remaining)
        if ms > 0
    }
