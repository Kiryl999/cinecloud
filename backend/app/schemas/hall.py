from typing import Annotated, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import NotNull


class HallCreate(BaseModel):
    """Rows and seats per row generate the seat grid.

    A hall without seats could never render a Saalplan, so the seats are
    materialised together with the hall rather than in a second call.
    """

    name: str = Field(min_length=1, max_length=100)
    rows: int = Field(gt=0, le=100)
    seats_per_row: int = Field(gt=0, le=100)


class HallUpdate(BaseModel):
    name: Annotated[Optional[str], NotNull] = Field(
        default=None, min_length=1, max_length=100
    )


class SeatRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    row_number: int
    seat_number: int


class HallRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cinema_id: int
    name: str
    seat_count: int


class HallDetail(HallRead):
    seats: List[SeatRead]
