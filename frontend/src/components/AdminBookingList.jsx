import { Link } from 'react-router-dom';

import { formatDay, formatPrice, formatTime, seatsByRow } from '../utils/format';

const when = (iso) => `${formatDay(iso)}, ${formatTime(iso)}`;

/** Bookings as the operator area lists them. With `programme`, each one also
    names its showtime and links to it. With `onSelect`, a booking can be
    picked, e.g. to find its seats on the seat map; `selected` is the
    reference of the picked one. */
function AdminBookingList({ bookings, programme, selected, onSelect }) {
  return (
    <ul className="admin-list">
      {bookings.map((booking) => {
        const showtime = programme?.showtimeById.get(booking.showtime_id);
        const isSelected = booking.reference === selected;
        return (
          <li
            key={booking.reference}
            id={`booking-${booking.reference}`}
            className={`admin-row${isSelected ? ' admin-row--selected' : ''}`}
          >
            <div className="admin-row__main">
              <strong className="admin-booking__reference">{booking.reference}</strong>
              {showtime && (
                <Link className="admin-booking__showtime" to={`/admin/showtimes/${showtime.id}`}>
                  {programme.movieById.get(showtime.movie_id)?.title},{' '}
                  {when(showtime.start_time)} ·{' '}
                  {programme.hallById.get(showtime.hall_id)?.name}
                </Link>
              )}
              <span>
                {seatsByRow(booking.seats)} · {formatPrice(booking.total_price)}
              </span>
              <span className="admin-row__meta">
                {booking.guest_email} · booked {when(booking.created_at)}
              </span>
            </div>
            {onSelect && (
              <div className="admin-row__actions">
                <button
                  type="button"
                  aria-pressed={isSelected}
                  onClick={() => onSelect(isSelected ? null : booking.reference)}
                >
                  {isSelected ? 'Hide seats' : 'Show seats'}
                </button>
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}

export default AdminBookingList;
