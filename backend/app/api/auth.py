from fastapi import APIRouter

from app.api.deps import CurrentAdmin, DbSession
from app.models.cinema import Cinema
from app.schemas.auth import AdminRead
from app.schemas.cinema import CinemaRead

# Signing in happens at Keycloak, so there is no login endpoint: the frontend
# sends the token Keycloak issued, and this tells it which cinema it manages.
router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/me", response_model=AdminRead)
async def read_current_admin(admin: CurrentAdmin, db: DbSession):
    # loaded here rather than with every admin, since only this endpoint needs it
    cinema = await db.get(Cinema, admin.cinema_id)
    return AdminRead(
        id=admin.id, cinema_id=admin.cinema_id, cinema=CinemaRead.model_validate(cinema)
    )
