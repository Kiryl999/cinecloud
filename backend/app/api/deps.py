from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.cinema_admin import CinemaAdmin

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

DbSession = Annotated[AsyncSession, Depends(get_db)]

_credentials_error = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_admin(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: DbSession,
) -> CinemaAdmin:
    try:
        payload = decode_access_token(token)
        admin_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError):
        raise _credentials_error

    admin = await db.get(CinemaAdmin, admin_id)
    if admin is None:
        raise _credentials_error
    return admin


CurrentAdmin = Annotated[CinemaAdmin, Depends(get_current_admin)]


async def get_current_tenant(admin: CurrentAdmin) -> int:
    """Single source of the tenant id - never taken from path or request body."""
    return admin.cinema_id


TenantId = Annotated[int, Depends(get_current_tenant)]
