import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import BookingConfirmation from "../components/BookingConfirmation";
import Checkout from "../components/Checkout";
import SeatGrid from "../components/SeatGrid";
import SiteFooter from "../components/SiteFooter";
import SiteHeader from "../components/SiteHeader";
import { useNow } from "../hooks/useNow";
import { effectiveStatus, useSeatStream } from "../hooks/useSeatStream";
import { bookingService, cinemaService } from "../services/api";
import { clearHold, loadHold, saveHold } from "../utils/holdStorage";
import { formatDayRelative, formatPrice, formatTime, seatsByRow } from "../utils/format";
import "../styles/Public.css";

const MAX_SEATS = 10;

/* Three steps on one page: pick seats, check out while they are held, see the
   booking. Correctness never depends on what this page shows - the server
   decides whether seats can be held and sold. */
function ShowtimePage() {
  const { slug, showtimeId } = useParams();
  const [showtime, setShowtime] = useState(null);
  const [error, setError] = useState(null);
  const { seats: liveSeats, live } = useSeatStream(slug, showtimeId);
  const now = useNow(1000);

  const [selected, setSelected] = useState(() => new Set());
  const [hold, setHold] = useState(() => loadHold(showtimeId));
  const [booking, setBooking] = useState(null);
  const [notice, setNotice] = useState(null);
  const [reserving, setReserving] = useState(false);

  // details for the header, and a clean 404 for a showtime that has started;
  // the seats come with the stream
  useEffect(() => {
    let cancelled = false;
    cinemaService
      .showtime(slug, showtimeId, { seats: false })
      .then((data) => {
        if (!cancelled) setShowtime(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [slug, showtimeId]);

  const seats = liveSeats ?? [];
  const free = new Set(
    seats.filter((seat) => effectiveStatus(seat, now) === "available").map((seat) => seat.id),
  );
  // a picked seat someone else takes in the meantime stops counting as picked
  const chosen = seats.filter((seat) => selected.has(seat.id) && free.has(seat.id));
  const lost = selected.size - chosen.length;

  // judged against the clock on every render, so an expired hold never shows
  const activeHold = hold && hold.deadline > now ? hold : null;
  const message =
    notice ?? (hold && !activeHold ? "Your reservation ran out. Please choose again." : null);

  function toggle(seat) {
    setNotice(null);
    if (hold && !activeHold) {
      // picking again acknowledges the expired reservation
      clearHold(showtimeId);
      setHold(null);
    }
    setSelected((current) => {
      const next = new Set([...current].filter((id) => free.has(id)));
      if (next.has(seat.id)) next.delete(seat.id);
      else if (next.size < MAX_SEATS) next.add(seat.id);
      return next;
    });
  }

  async function reserve() {
    setReserving(true);
    setNotice(null);
    try {
      const result = await bookingService.hold(
        slug,
        showtimeId,
        chosen.map((seat) => seat.id),
      );
      const newHold = {
        token: result.hold_token,
        seatIds: result.seat_ids,
        deadline: Date.now() + result.expires_in * 1000,
      };
      saveHold(showtimeId, newHold);
      setHold(newHold);
      setSelected(new Set());
    } catch (err) {
      setNotice(
        err.status === 409
          ? "Someone was faster: at least one of these seats was just taken."
          : err.message,
      );
    } finally {
      setReserving(false);
    }
  }

  async function book(email) {
    try {
      const result = await bookingService.book(slug, showtimeId, activeHold.token, email);
      clearHold(showtimeId);
      setHold(null);
      setBooking(result);
    } catch (err) {
      if (err.status !== 409) throw err; // shown inside the checkout
      clearHold(showtimeId);
      setHold(null);
      setNotice("Your reservation ran out before the booking went through. Please choose again.");
    }
  }

  const seatsOf = (ids) => seats.filter((seat) => ids.includes(seat.id));
  const step = booking ? 3 : activeHold ? 2 : 1;
  const total = Number(showtime?.ticket_price ?? 0) * chosen.length;

  return (
    <div className="page">
      <SiteHeader />

      <main className="page__body">
        <Link to={`/cinemas/${slug}`} className="back">
          Programme
        </Link>

        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        {!showtime && !error && <p className="status">Loading the showtime…</p>}

        {showtime && (
          <>
            <h1 className="title">{showtime.movie.title}</h1>
            <p className="subtitle">
              {formatDayRelative(showtime.start_time)} at {formatTime(showtime.start_time)} in{" "}
              {showtime.hall.name}, {formatPrice(showtime.ticket_price)} per seat
            </p>

            <ol className="steps" aria-label="Booking steps">
              {["Choose seats", "Your details", "Booked"].map((label, index) => (
                <li
                  key={label}
                  className={index + 1 < step ? "steps__done" : undefined}
                  aria-current={index + 1 === step ? "step" : undefined}
                >
                  {label}
                </li>
              ))}
            </ol>

            {booking ? (
              <BookingConfirmation booking={booking} seats={seatsOf(booking.seat_ids)} slug={slug} />
            ) : activeHold ? (
              <Checkout
                seats={seatsOf(activeHold.seatIds)}
                ticketPrice={showtime.ticket_price}
                remainingMs={activeHold.deadline - now}
                onBook={book}
              />
            ) : (
              <div className="booking">
                <section className="seatmap" aria-label="Seat map">
                  <div className="seatmap__screen" aria-hidden="true">
                    Screen
                  </div>

                  <SeatGrid
                    seats={seats}
                    stateOf={(seat) =>
                      chosen.includes(seat) ? "chosen" : free.has(seat.id) ? "free" : "taken"
                    }
                    onToggle={toggle}
                  />

                  <ul className="seatmap__legend">
                    <li>
                      <span className="seat seat--free" aria-hidden="true" /> Free
                    </li>
                    <li>
                      <span className="seat seat--chosen" aria-hidden="true" /> Your seats
                    </li>
                    <li>
                      <span className="seat seat--taken" aria-hidden="true" /> Taken
                    </li>
                    <li className={live ? "live" : "live live--off"}>
                      {live ? "Updates live" : "Connecting…"}
                    </li>
                  </ul>
                </section>

                <aside className="selection" aria-label="Your selection">
                  {message && (
                    <p className="error" role="status">
                      {message}
                    </p>
                  )}
                  {lost > 0 && (
                    <p className="error" role="status">
                      Someone else just took{" "}
                      {lost === 1 ? "one of your seats" : `${lost} of your seats`}.
                    </p>
                  )}

                  {chosen.length === 0 ? (
                    <p className="selection__hint">
                      Choose the seats you want, up to {MAX_SEATS}. They are held for you
                      for 10 minutes once you reserve them.
                    </p>
                  ) : (
                    <>
                      <p className="selection__seats">{seatsByRow(chosen)}</p>
                      <p className="selection__total">
                        {chosen.length} {chosen.length === 1 ? "seat" : "seats"},{" "}
                        <strong>{formatPrice(total)}</strong>
                      </p>
                      <button
                        type="button"
                        className="button"
                        disabled={reserving}
                        onClick={reserve}
                      >
                        {reserving ? "Reserving…" : "Reserve seats"}
                      </button>
                    </>
                  )}
                </aside>
              </div>
            )}
          </>
        )}
      </main>

      <SiteFooter />
    </div>
  );
}

export default ShowtimePage;
