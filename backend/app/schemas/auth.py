from pydantic import BaseModel, ConfigDict

from app.schemas.cinema import CinemaRead


class AdminRead(BaseModel):
    """Response schema for admins.

    Name and e-mail are not here: they belong to the Keycloak account, and the
    frontend reads them from the ID token.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    cinema_id: int
    # for the operator area's header and its link to the visitor pages
    cinema: CinemaRead
