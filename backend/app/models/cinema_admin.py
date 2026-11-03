from datetime import datetime, timezone
from sqlalchemy import Column, DateTime
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional

class CinemaAdmin(SQLModel, table=True):
    """Links a Keycloak account to the cinema it manages.

    The account itself - e-mail, password, passkeys - lives in Keycloak.
    """

    __tablename__ = "cinema_admins"

    id: Optional[int] = Field(default=None, primary_key=True)
    cinema_id: int = Field(foreign_key="cinemas.id")
    # the `sub` claim of the account's tokens: Keycloak's user id, which
    # unlike the e-mail address never changes
    subject: str = Field(index=True, unique=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    cinema: Optional["Cinema"] = Relationship(back_populates="admins")
