from enum import Enum

class BookingStatus(str, Enum):
    pending = "pending"
    confirmed = "confirmed"
    cancelled = "cancelled"

class SeatStatus(str, Enum):
    available = "available"
    held = "held"
    booked = "booked"
