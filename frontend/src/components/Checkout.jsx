import { useState } from "react";

import { formatCountdown, formatPrice, seatsByRow } from "../utils/format";

// how long the server holds seats (HOLD_SECONDS in backend/app/services/seat_holds.py)
const HOLD_MS = 10 * 60 * 1000;
// from here on the countdown asks for attention
const HURRY_MS = 2 * 60 * 1000;

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

  const left = Math.max(0, Math.min(1, remainingMs / HOLD_MS));

  return (
    <form className="panel checkout" onSubmit={handleSubmit}>
      <div className={remainingMs < HURRY_MS ? "hold hold--hurry" : "hold"}>
        <p>
          Your seats are held for <strong className="hold__time">{formatCountdown(remainingMs)}</strong>
        </p>
        <div className="hold__bar" aria-hidden="true">
          <span style={{ transform: `scaleX(${left})` }} />
        </div>
      </div>

      <p className="checkout__seats">{seatsByRow(seats)}</p>
      <p className="checkout__total">
        {seats.length} {seats.length === 1 ? "seat" : "seats"},{" "}
        <strong>{formatPrice(Number(ticketPrice) * seats.length)}</strong>
      </p>

      <div className="field">
        <label htmlFor="guest-email">E-mail for your tickets</label>
        <input
          id="guest-email"
          className="input"
          type="email"
          value={email}
          autoComplete="email"
          placeholder="you@example.com"
          required
          onChange={(event) => setEmail(event.target.value)}
        />
      </div>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      <button type="submit" className="button" disabled={submitting}>
        {submitting ? "Booking…" : "Pay and book"}
      </button>
      <p className="checkout__note">
        This is a demo: the payment is simulated and nothing is charged.
      </p>
    </form>
  );
}

export default Checkout;
