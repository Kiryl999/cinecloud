import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import BookingConfirmation from "../components/BookingConfirmation";
import Checkout from "../components/Checkout";
import SeatGrid from "../components/SeatGrid";
import SiteHeader from "../components/SiteHeader";
import { useNow } from "../hooks/useNow";
import { effectiveStatus, toSeats, useSeatStream } from "../hooks/useSeatStream";
import { bookingService, cinemaService } from "../services/api";
import { clearHold, loadHold, saveHold } from "../utils/holdStorage";
import { formatDay, formatPrice, formatTime, seatLabel } from "../utils/format";
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

  // details for the header, and a clean 404 for a showtime that has started
  useEffect(() => {
    let cancelled = false;
    cinemaService
      .showtime(slug, showtimeId)
      .then((data) => {
        if (!cancelled) setShowtime({ ...data, seats: toSeats(data.seats) });
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [slug, showtimeId]);

  // the live stream takes over as soon as its first snapshot arrives
  const seats = liveSeats ?? showtime?.seats ?? [];
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

  return (
    <div className="page">
      <SiteHeader />

      <main className="page__body">
        <Link to={`/cinemas/${slug}`} className="page__back">
          ← Programme
        </Link>

        {error && <p className="page__error">{error}</p>}
        {!showtime && !error && <p className="page__status">Loading seats…</p>}

        {showtime && (
          <>
            <span className="page__eyebrow">
              {formatDay(showtime.start_time)} · {formatTime(showtime.start_time)} ·{" "}
              {showtime.hall.name}
            </span>
            <h1>{showtime.movie.title}</h1>

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
              <>
                <div className="seatmap">
                  <div className="seatmap__screen">Screen</div>

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
                      <span className="seat seat--chosen" aria-hidden="true" /> Your pick
                    </li>
                    <li>
                      <span className="seat seat--taken" aria-hidden="true" /> Taken
                    </li>
                    <li className={live ? "seatmap__live" : "seatmap__live seatmap__live--off"}>
                      {live ? "Live" : "Connecting…"}
                    </li>
                  </ul>
                </div>

                <aside className="selection">
                  {message && (
                    <p className="page__error" role="status">
                      {message}
                    </p>
                  )}
                  {lost > 0 && (
                    <p className="page__error" role="status">
                      Someone else just took{" "}
                      {lost === 1 ? "one of your seats" : `${lost} of your seats`}.
                    </p>
                  )}

                  {chosen.length === 0 ? (
                    <p className="page__status">
                      Pick up to {MAX_SEATS} seats · {formatPrice(showtime.ticket_price)} each
                    </p>
                  ) : (
                    <>
                      <p className="selection__seats">{chosen.map(seatLabel).join(", ")}</p>
                      <p className="selection__total">
                        {chosen.length} {chosen.length === 1 ? "seat" : "seats"} ·{" "}
                        {formatPrice(Number(showtime.ticket_price) * chosen.length)}
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
              </>
            )}
          </>
        )}
      </main>
    </div>
  );
}

export default ShowtimePage;
