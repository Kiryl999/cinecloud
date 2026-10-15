import { Link } from "react-router-dom";

import { formatPrice, seatLabel } from "../utils/format";

/** Last step: the sale is recorded, the reference is what the guest keeps. */
function BookingConfirmation({ booking, seats, slug }) {
  return (
    <section className="confirmation">
      <span className="page__eyebrow">Booked</span>
      <p className="confirmation__reference">{booking.reference}</p>
      <p className="page__status">Your booking reference - keep it for the entrance.</p>

      <ul className="checkout__seats">
        {seats.map((seat) => (
          <li key={seat.id}>{seatLabel(seat)}</li>
        ))}
      </ul>
      <p className="selection__total">{formatPrice(booking.total_price)}</p>
      <p className="page__status">Booked for {booking.guest_email}</p>

      <Link to={`/cinemas/${slug}`} className="page__back">
        ← Back to the programme
      </Link>
    </section>
  );
}

export default BookingConfirmation;
