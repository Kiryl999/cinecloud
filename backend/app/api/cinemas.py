from fastapi import APIRouter
from sqlmodel import select

from app.api.deps import DbSession
from app.models.cinema import Cinema
from app.schemas.cinema import CinemaRead

router = APIRouter(prefix="/cinemas", tags=["cinemas"])


@router.get("/", response_model=list[CinemaRead])
async def list_cinemas(db: DbSession):
    result = await db.execute(select(Cinema))
    return result.scalars().all()
