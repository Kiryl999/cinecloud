from fastapi import APIRouter

from app.api.deps import CurrentAdmin
from app.schemas.auth import AdminRead

# Signing in happens at Keycloak, so there is no login endpoint: the frontend
# sends the token Keycloak issued, and this tells it which cinema it manages.
router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/me", response_model=AdminRead)
async def read_current_admin(admin: CurrentAdmin):
    return admin
