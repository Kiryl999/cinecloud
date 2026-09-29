from datetime import datetime
from decimal import Decimal
from typing import Annotated, Optional

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.schemas.common import NotNull


class ShowtimeCreate(BaseModel):
    """movie_id and hall_id are verified against the caller's cinema before use.

    start_time must carry a UTC offset. Without one, Python reads it as the
    server's local time - Berlin on a developer laptop, UTC in a container - so
    the same request would store different instants depending on where it runs.
    """

    movie_id: int
    hall_id: int
    start_time: AwareDatetime
    ticket_price: Decimal = Field(ge=0, max_digits=5, decimal_places=2)


class ShowtimeUpdate(BaseModel):
    movie_id: Annotated[Optional[int], NotNull] = None
    start_time: Annotated[Optional[AwareDatetime], NotNull] = None
    ticket_price: Annotated[Optional[Decimal], NotNull] = Field(
        default=None, ge=0, max_digits=5, decimal_places=2
    )


class ShowtimeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cinema_id: int
    movie_id: int
    hall_id: int
    start_time: datetime
    ticket_price: Decimal
