from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import select

from app.api.deps import CurrentAdmin, DbSession
from app.core.security import create_access_token, verify_password
from app.models.cinema_admin import CinemaAdmin
from app.schemas.auth import AdminRead, Token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DbSession,
):
    result = await db.execute(
        select(CinemaAdmin).where(CinemaAdmin.email == form_data.username)
    )
    admin = result.scalar_one_or_none()

    # same error for "unknown admin" and "wrong password" so the endpoint
    # cannot be used to probe which e-mail addresses exist
    if admin is None or not verify_password(form_data.password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return Token(access_token=create_access_token(admin.id, admin.cinema_id))


@router.get("/me", response_model=AdminRead)
async def read_current_admin(admin: CurrentAdmin):
    return admin
