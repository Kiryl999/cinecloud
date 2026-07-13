from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.database import get_db
from app.models.cinema import Cinema
from backend.app.models.hall import Screen

router = APIRouter(prefix="/cinemas", tags=["cinemas"])

@router.get("/")
async def list_cinemas(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Cinema))
    return result.scalars().all()