import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import SiteHeader from "../components/SiteHeader";
import { cinemaService } from "../services/api";
import { formatDay, formatPrice, formatTime } from "../utils/format";
import "../styles/Public.css";

// The plan is re-fetched while someone is choosing, so seats others take show
// up within a few seconds. Correctness never depends on it: the server decides
// whether seats can actually be reserved.
const REFRESH_MS = 5000;
const MAX_SEATS = 10;

function groupByRow(seats) {
  const rows = new Map();
  for (const seat of seats) {
    if (!rows.has(seat.row_number)) rows.set(seat.row_number, []);
    rows.get(seat.row_number).push(seat);
  }
  return [...rows.entries()];
}

function SeatGrid({ seats, isChosen, onToggle }) {
  return (
    // A wide hall must stay scrollable to its first seat, hence the wrapper
    <div className="seatmap__scroll">
      <div className="seatmap__rows">
        {groupByRow(seats).map(([row, rowSeats]) => (
          <div className="seatmap__row" key={row}>
            <span className="seatmap__label">{row}</span>
            {rowSeats.map((seat) => {
              const chosen = isChosen(seat);
              const state = chosen ? "chosen" : seat.status === "available" ? "free" : "taken";
              return (
                <button
                  key={seat.id}
                  type="button"
                  className={`seat seat--${state}`}
                  disabled={state === "taken"}
                  aria-pressed={chosen}
                  aria-label={`Row ${row}, seat ${seat.seat_number}, ${state}`}
                  onClick={() => onToggle(seat)}
                >
                  {seat.seat_number}
                </button>
              );
            })}
            <span className="seatmap__label">{row}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function ShowtimePage() {
  const { slug, showtimeId } = useParams();
  const [showtime, setShowtime] = useState(null);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(() => new Set());

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const data = await cinemaService.showtime(slug, showtimeId);
        if (cancelled) return;
        setShowtime(data);
        setError(null);
      } catch (err) {
        if (!cancelled) setError(err.message);
      }
    }

    load();
    // no point refreshing a tab nobody is looking at
    const timer = setInterval(() => {
      if (!document.hidden) load();
    }, REFRESH_MS);

    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [slug, showtimeId]);

  const seats = showtime?.seats ?? [];
  const available = new Set(
    seats.filter((seat) => seat.status === "available").map((seat) => seat.id),
  );
  // A picked seat can be taken by someone else between two refreshes. It then
  // simply stops counting as picked; the next click clears it for good.
  const chosen = seats.filter((seat) => selected.has(seat.id) && available.has(seat.id));
  const lost = selected.size - chosen.length;

  function toggle(seat) {
    setSelected((current) => {
      const next = new Set([...current].filter((id) => available.has(id)));
      if (next.has(seat.id)) next.delete(seat.id);
      else if (next.size < MAX_SEATS) next.add(seat.id);
      return next;
    });
  }

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

            <div className="seatmap">
              <div className="seatmap__screen">Screen</div>

              <SeatGrid
                seats={seats}
                isChosen={(seat) => selected.has(seat.id) && available.has(seat.id)}
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
              </ul>
            </div>

            <aside className="selection">
              {lost > 0 && (
                <p className="page__error" role="status">
                  Someone else just took {lost === 1 ? "one of your seats" : `${lost} of your seats`}.
                </p>
              )}
              {chosen.length === 0 ? (
                <p className="page__status">
                  Pick up to {MAX_SEATS} seats · {formatPrice(showtime.ticket_price)} each
                </p>
              ) : (
                <>
                  <p className="selection__seats">
                    {chosen
                      .map((seat) => `Row ${seat.row_number} · Seat ${seat.seat_number}`)
                      .join(", ")}
                  </p>
                  <p className="selection__total">
                    {chosen.length} {chosen.length === 1 ? "seat" : "seats"} ·{" "}
                    {formatPrice(Number(showtime.ticket_price) * chosen.length)}
                  </p>
                </>
              )}
            </aside>
          </>
        )}
      </main>
    </div>
  );
}

export default ShowtimePage;
