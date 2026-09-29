"""Single choke point for tenant-scoped lookups.

Every read of a tenant-owned row goes through here, so the rule "an admin only
ever reaches its own cinema's data" lives in one place instead of being repeated
- and eventually forgotten - in every endpoint.

A row that does not exist and a row owned by another cinema both raise 404.
Returning 403 for the second case would confirm that the id exists and turn the
endpoint into an oracle for probing other tenants' data.
"""

from typing import TypeVar

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel

# only models carrying a cinema_id discriminator can be scoped directly
# seats and showtime_seats reach their tenant through hall / showtime instead
T = TypeVar("T", bound=SQLModel)


async def get_owned_or_404(
    db: AsyncSession,
    model: type[T],
    obj_id: int,
    tenant_id: int,
    *,
    name: str,
) -> T:
    """Load `model` by primary key, but only if it belongs to `tenant_id`."""
    obj = await db.get(model, obj_id)
    if obj is None or obj.cinema_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{name} not found",
        )
    return obj
