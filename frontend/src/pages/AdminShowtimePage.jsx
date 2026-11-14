import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import AdminBookingList from '../components/AdminBookingList';
import SeatGrid from '../components/SeatGrid';
import { useAuth } from '../hooks/useAuth';
import { useNow } from '../hooks/useNow';
import { useProgramme } from '../hooks/useProgramme';
import { effectiveStatus, toSeats } from '../hooks/useSeatStream';
import { cinemaService, salesService, showtimeService } from '../services/api';
import { formatDay, formatPrice, formatTime } from '../utils/format';

// a showtime has at most as many bookings as seats; the API's upper bound
const BOOKINGS_LIMIT = 1000;
// at most this often, however busy the seat map gets
const RELOAD_INTERVAL_MS = 500;

/** One showtime from the cinema's side: which seats are sold, which are held
    by guests checking out right now, and who booked what. */
function AdminShowtimePage() {
  const showtimeId = Number(useParams().showtimeId);
  const { admin } = useAuth();
  const { programme } = useProgramme();
  const showtime = programme.showtimeById.get(showtimeId);
  const now = useNow(1000);

  const [sales, setSales] = useState(null);
  const [error, setError] = useState(null);
  const [live, setLive] = useState(false);
  // reference of the booking whose seats are highlighted
  const [selected, setSelected] = useState(null);

  const load = useCallback(async () => {
    const [seats, bookings] = await Promise.all([
      showtimeService.seats(showtimeId),
      salesService.bookings({ showtimeId, limit: BOOKINGS_LIMIT }),
    ]);
    setSales({ seats: toSeats(seats), bookings });
    setError(null);
  }, [showtimeId]);

  useEffect(() => {
    load().catch((err) => setError(err.message));
  }, [load]);

  // Until it starts, the visitors' live stream announces every hold and
  // sale; each one reloads the seats and bookings from the operator API.
  const upcoming = Boolean(showtime) && new Date(showtime.start_time) > now;
  const slug = admin?.cinema?.slug;
  useEffect(() => {
    if (!upcoming || !slug) return undefined;
    const source = new EventSource(cinemaService.seatStreamUrl(slug, showtimeId));
    let timer = null;
    source.addEventListener('snapshot', () => setLive(true));
    source.addEventListener('seats', () => {
      timer ??= setTimeout(() => {
        timer = null;
        load().catch((err) => setError(err.message));
      }, RELOAD_INTERVAL_MS);
    });
    source.onerror = () => setLive(false);
    return () => {
      clearTimeout(timer);
      source.close();
      setLive(false);
    };
  }, [upcoming, slug, showtimeId, load]);

  // a booking picked on the seat map may be far down the list
  useEffect(() => {
    if (!selected) return;
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    document
      .getElementById(`booking-${selected}`)
      ?.scrollIntoView({ block: 'nearest', behavior: reduceMotion ? 'auto' : 'smooth' });
  }, [selected]);

  const bookingOfSeat = useMemo(() => {
    const owner = new Map();
    for (const booking of sales?.bookings ?? []) {
      for (const seat of booking.seats) owner.set(seat.id, booking.reference);
    }
    return owner;
  }, [sales]);

  if (!showtime) {
    return (
      <>
        <Link className="admin__back" to="/admin/showtimes">
          ← Showtimes
        </Link>
        <p className="admin-empty">This showtime does not exist (any more).</p>
      </>
    );
  }

  const movie = programme.movieById.get(showtime.movie_id);
  const hall = programme.hallById.get(showtime.hall_id);
  const ends = new Date(showtime.start_time).getTime() + movie.duration_minutes * 60_000;

  function stateOf(seat) {
    const status = effectiveStatus(seat, now);
    if (status === 'booked') {
      return bookingOfSeat.get(seat.id) === selected ? 'chosen' : 'sold';
    }
    return status === 'held' ? 'held' : 'free';
  }

  const states = sales ? sales.seats.map(stateOf) : [];
  const sold = states.filter((state) => state === 'sold' || state === 'chosen').length;
  const held = states.filter((state) => state === 'held').length;
  const revenue = (sales?.bookings ?? []).reduce((sum, b) => sum + Number(b.total_price), 0);

  return (
    <>
      <Link className="admin__back" to="/admin/showtimes">
        ← Showtimes
      </Link>
      <h1>{movie.title}</h1>
      <p className="admin__lead">
        {formatDay(showtime.start_time)}, {formatTime(showtime.start_time)}–{formatTime(ends)} ·{' '}
        {hall.name} · {formatPrice(showtime.ticket_price)} per seat
      </p>

      {error && (
        <p className="admin-login__error" role="alert">
          {error}
        </p>
      )}

      {sales && (
        <>
          <div className="admin__cards">
            <div className="admin__card">
              <span className="admin__count">
                {sold}
                <small> / {sales.seats.length}</small>
              </span>
              <h2>Seats sold</h2>
            </div>
            <div className="admin__card">
              <span className="admin__count">{held}</span>
              <h2>Held right now</h2>
            </div>
            <div className="admin__card">
              <span className="admin__count">{formatPrice(revenue)}</span>
              <h2>Revenue</h2>
            </div>
          </div>

          <section className="admin-seatmap seatmap" aria-label="Seat map">
            <div className="seatmap__screen">Screen</div>
            <SeatGrid
              seats={sales.seats}
              stateOf={stateOf}
              disabledStates={['free', 'held']}
              onToggle={(seat) => {
                const reference = bookingOfSeat.get(seat.id);
                if (reference) setSelected((current) => (current === reference ? null : reference));
              }}
            />
            <ul className="seatmap__legend">
              <li>
                <span className="seat seat--free" aria-hidden="true" /> Free
              </li>
              <li>
                <span className="seat seat--held" aria-hidden="true" /> Held by a guest
              </li>
              <li>
                <span className="seat seat--sold" aria-hidden="true" /> Sold
              </li>
              <li>
                {upcoming ? (
                  <span className={live ? 'seatmap__live' : 'seatmap__live seatmap__live--off'}>
                    {live ? 'Live' : 'Connecting…'}
                  </span>
                ) : (
                  'Started - no more bookings'
                )}
              </li>
            </ul>
            <p className="admin-manage__note admin-seatmap__hint">
              Click a sold seat to see who booked it.
            </p>
          </section>

          <h2 className="admin__heading">
            {sales.bookings.length === 1 ? '1 booking' : `${sales.bookings.length} bookings`}
          </h2>
          {sales.bookings.length === 0 ? (
            <p className="admin-empty">Nobody has booked this showtime yet.</p>
          ) : (
            <AdminBookingList
              bookings={sales.bookings}
              selected={selected}
              onSelect={setSelected}
            />
          )}
        </>
      )}
      {!sales && !error && <p className="admin-status">Loading seats…</p>}
    </>
  );
}

export default AdminShowtimePage;
