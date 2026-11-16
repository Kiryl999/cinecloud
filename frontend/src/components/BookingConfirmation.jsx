import { Link } from "react-router-dom";

import { formatPrice, seatsByRow } from "../utils/format";

/** Last step: the sale is recorded, the reference is what the guest keeps. */
function BookingConfirmation({ booking, seats, slug }) {
  return (
    <section className="panel confirmation" aria-labelledby="booking-reference">
      <h2>You are booked</h2>
      <p className="confirmation__label">Booking reference, shown at the entrance</p>
      <p className="confirmation__reference" id="booking-reference">
        {booking.reference}
      </p>

      <p className="checkout__seats">{seatsByRow(seats)}</p>
      <p className="checkout__total">
        Paid <strong>{formatPrice(booking.total_price)}</strong>
      </p>

      <p className="confirmation__mail">
        A confirmation is on its way to <strong>{booking.guest_email}</strong>. In this demo
        no mail leaves the server: every one of them lands in the{" "}
        <a href="/mail/">demo mailbox</a>.
      </p>

      <Link to={`/cinemas/${slug}`} className="button button--quiet">
        Back to the programme
      </Link>
    </section>
  );
}

export default BookingConfirmation;
