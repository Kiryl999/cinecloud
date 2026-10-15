import { useState } from "react";

import { formatCountdown, formatPrice, seatLabel } from "../utils/format";

/** Second step: the seats are held, the guest leaves an e-mail and pays. */
function Checkout({ seats, ticketPrice, remainingMs, onBook }) {
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  async function handleSubmit(event) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await onBook(email);
    } catch (err) {
      setError(err.message);
      setSubmitting(false);
    }
  }

  return (
    <form className="checkout" onSubmit={handleSubmit}>
      <p className="checkout__timer">
        Your seats are reserved for <strong>{formatCountdown(remainingMs)}</strong>
      </p>

      <ul className="checkout__seats">
        {seats.map((seat) => (
          <li key={seat.id}>{seatLabel(seat)}</li>
        ))}
      </ul>
      <p className="selection__total">
        {seats.length} {seats.length === 1 ? "seat" : "seats"} ·{" "}
        {formatPrice(Number(ticketPrice) * seats.length)}
      </p>

      <label htmlFor="guest-email">E-mail for your booking</label>
      <input
        id="guest-email"
        type="email"
        value={email}
        autoComplete="email"
        required
        onChange={(event) => setEmail(event.target.value)}
      />

      {error && (
        <p className="page__error" role="alert">
          {error}
        </p>
      )}

      <button type="submit" className="button" disabled={submitting}>
        {submitting ? "Booking…" : "Pay and book"}
      </button>
      <p className="checkout__note">Payment is simulated - no money changes hands.</p>
    </form>
  );
}

export default Checkout;
