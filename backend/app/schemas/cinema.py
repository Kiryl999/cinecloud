from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CinemaCreate(BaseModel):
    """A new cinema, opened by the account that is going to manage it."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)
    # the cinema's address on the visitor pages, /cinemas/<slug>: lower-case
    # letters and digits, words joined by single hyphens
    slug: str = Field(min_length=2, max_length=60, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    # a week of programme to start with, see app/services/demo.py
    demo_programme: bool = False


class CinemaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    created_at: datetime
