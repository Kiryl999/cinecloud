import { Link } from 'react-router-dom';

import { useAuth } from '../hooks/useAuth';
import { useNow } from '../hooks/useNow';
import { useProgramme } from '../hooks/useProgramme';
import { formatDay, formatTime } from '../utils/format';

/** What a new cinema still lacks before it can sell a ticket, in the order
    it has to be added: a showtime needs a movie and a hall. */
function nextStep({ halls, movies, showtimes }) {
  if (halls.length === 0) return { to: '/admin/halls', text: 'Add your first hall' };
  if (movies.length === 0) return { to: '/admin/movies', text: 'Add your first movie' };
  if (showtimes.length === 0) return { to: '/admin/showtimes', text: 'Plan your first showtime' };
  return null;
}

function AdminDashboardPage() {
  const { admin } = useAuth();
  const { programme } = useProgramme();
  const now = useNow(60_000);
  const cinema = admin?.cinema;

  // the API sends them ordered by start time
  const upcoming = programme.showtimes.filter((s) => new Date(s.start_time) > now);
  const step = nextStep(programme);
  const ticketsSold = upcoming.reduce((sum, showtime) => sum + showtime.seats_sold, 0);

  return (
    <>
      <h1>Overview</h1>

      <div className="admin__cards">
        <Link className="admin__card" to="/admin/showtimes">
          <span className="admin__count">{upcoming.length}</span>
          <h2>Upcoming showtimes</h2>
        </Link>
        <Link className="admin__card" to="/admin/bookings">
          <span className="admin__count">{ticketsSold}</span>
          <h2>Tickets sold for them</h2>
        </Link>
        <Link className="admin__card" to="/admin/movies">
          <span className="admin__count">{programme.movies.length}</span>
          <h2>Movies</h2>
        </Link>
        <Link className="admin__card" to="/admin/halls">
          <span className="admin__count">{programme.halls.length}</span>
          <h2>Halls</h2>
        </Link>
      </div>

      {cinema && (
        <p className="admin__public">
          Visitors find your cinema at{' '}
          <Link to={`/cinemas/${cinema.slug}`}>
            {window.location.host}/cinemas/{cinema.slug}
          </Link>
        </p>
      )}

      {step ? (
        <p className="admin-empty">
          Nothing to book yet. <Link to={step.to}>{step.text}</Link>
        </p>
      ) : (
        <section className="admin__next">
          <h2 className="admin__heading">Coming up</h2>
          {upcoming.length === 0 ? (
            <p className="admin-empty">
              Every showtime is in the past. <Link to="/admin/showtimes">Plan new ones</Link>
            </p>
          ) : (
            <ul className="admin-list">
              {upcoming.slice(0, 5).map((showtime) => (
                <li key={showtime.id} className="admin-row">
                  <div className="admin-row__main">
                    <Link className="admin-row__title" to={`/admin/showtimes/${showtime.id}`}>
                      {programme.movieById.get(showtime.movie_id)?.title}
                    </Link>
                    <span className="admin-row__meta">
                      {formatDay(showtime.start_time)}, {formatTime(showtime.start_time)} ·{' '}
                      {programme.hallById.get(showtime.hall_id)?.name} · {showtime.seats_sold} /{' '}
                      {programme.hallById.get(showtime.hall_id)?.seat_count} sold
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </>
  );
}

export default AdminDashboardPage;
