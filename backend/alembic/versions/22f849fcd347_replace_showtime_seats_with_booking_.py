"""replace showtime_seats with booking_seats

showtime_seats held one row per seat per showtime, mainly to carry the temporary
hold (status 'held', held_until). Holds move to Redis, which leaves sales as the
only thing the database has to record: booking_seats stores a row only for a
sold seat, and its unique constraint guarantees a seat is sold at most once per
showtime.

Sold seats are carried over in both directions. Holds are not - they are
temporary by nature and are dropped with the old table.

Revision ID: 22f849fcd347
Revises: e95392bad0bf
Create Date: 2026-10-07 17:39:49.888596

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '22f849fcd347'
down_revision: Union[str, Sequence[str], None] = 'e95392bad0bf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # must exist before booking_seats: it is the target of the composite FK
    op.create_unique_constraint('uq_booking_id_showtime', 'bookings', ['id', 'showtime_id'])

    op.create_table('booking_seats',
    sa.Column('booking_id', sa.Integer(), nullable=False),
    sa.Column('seat_id', sa.Integer(), nullable=False),
    sa.Column('showtime_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['booking_id', 'showtime_id'], ['bookings.id', 'bookings.showtime_id'], name='fk_booking_seats_booking'),
    sa.ForeignKeyConstraint(['seat_id'], ['seats.id'], ),
    sa.ForeignKeyConstraint(['showtime_id'], ['showtimes.id'], ),
    sa.PrimaryKeyConstraint('booking_id', 'seat_id'),
    sa.UniqueConstraint('showtime_id', 'seat_id', name='uq_booking_seat_per_showtime')
    )

    op.execute("""
        INSERT INTO booking_seats (booking_id, seat_id, showtime_id)
        SELECT booking_id, seat_id, showtime_id
        FROM showtime_seats
        WHERE status = 'booked' AND booking_id IS NOT NULL
    """)

    op.drop_table('showtime_seats')


def downgrade() -> None:
    """Downgrade schema."""
    op.create_table('showtime_seats',
    sa.Column('id', sa.INTEGER(), autoincrement=True, nullable=False),
    sa.Column('showtime_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('seat_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('booking_id', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('status', sa.VARCHAR(), server_default=sa.text("'available'::character varying"), autoincrement=False, nullable=False),
    sa.Column('held_until', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['booking_id'], ['bookings.id'], name=op.f('showtime_seats_booking_id_fkey')),
    sa.ForeignKeyConstraint(['seat_id'], ['seats.id'], name=op.f('showtime_seats_seat_id_fkey')),
    sa.ForeignKeyConstraint(['showtime_id'], ['showtimes.id'], name=op.f('showtime_seats_showtime_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('showtime_seats_pkey')),
    sa.UniqueConstraint('showtime_id', 'seat_id', name=op.f('uq_showtime_seat'))
    )

    # the old model kept a row for every seat of every showtime, sold or not
    op.execute("""
        INSERT INTO showtime_seats (showtime_id, seat_id, booking_id, status)
        SELECT showtimes.id,
               seats.id,
               booking_seats.booking_id,
               CASE WHEN booking_seats.booking_id IS NULL THEN 'available' ELSE 'booked' END
        FROM showtimes
        JOIN seats ON seats.hall_id = showtimes.hall_id
        LEFT JOIN booking_seats
               ON booking_seats.showtime_id = showtimes.id
              AND booking_seats.seat_id = seats.id
    """)

    # booking_seats first: its foreign key depends on the constraint below
    op.drop_table('booking_seats')
    op.drop_constraint('uq_booking_id_showtime', 'bookings', type_='unique')
