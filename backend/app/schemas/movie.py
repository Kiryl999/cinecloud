from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import NotNull

# cinema_id is deliberately absent from the write schemas: the tenant is taken
# from the access token, never from client input.


class MovieCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    release_year: int = Field(ge=1888, le=2200)
    duration_minutes: int = Field(gt=0, le=1000)
    poster_key: Optional[str] = Field(default=None, max_length=500)


class MovieUpdate(BaseModel):
    """PATCH payload - only the fields actually sent are applied.

    poster_key is the one nullable column: sending null removes the poster.
    """

    title: Annotated[Optional[str], NotNull] = Field(
        default=None, min_length=1, max_length=200
    )
    description: Annotated[Optional[str], NotNull] = Field(
        default=None, max_length=2000
    )
    release_year: Annotated[Optional[int], NotNull] = Field(
        default=None, ge=1888, le=2200
    )
    duration_minutes: Annotated[Optional[int], NotNull] = Field(
        default=None, gt=0, le=1000
    )
    poster_key: Optional[str] = Field(default=None, max_length=500)


class MovieRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cinema_id: int
    title: str
    description: str
    release_year: int
    duration_minutes: int
    poster_key: Optional[str]
