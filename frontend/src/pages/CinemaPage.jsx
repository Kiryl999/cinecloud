import { useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import SiteFooter from "../components/SiteFooter";
import SiteHeader from "../components/SiteHeader";
import { cinemaService } from "../services/api";
import {
  dayKey,
  formatDay,
  formatDayRelative,
  formatDuration,
  formatPrice,
  formatTime,
} from "../utils/format";
import "../styles/Public.css";

/** Showtimes by day, and within a day by film, films in order of their first showtime. */
function groupByDay(showtimes) {
  const days = new Map();
  for (const showtime of showtimes) {
    const key = dayKey(showtime.start_time);
    if (!days.has(key)) days.set(key, new Map());
    const films = days.get(key);
    if (!films.has(showtime.movie.id)) films.set(showtime.movie.id, { movie: showtime.movie, showtimes: [] });
    films.get(showtime.movie.id).showtimes.push(showtime);
  }
  return [...days].map(([key, films]) => ({
    key,
    first: [...films.values()][0].showtimes[0].start_time,
    films: [...films.values()],
  }));
}

function CinemaPage() {
  const { slug } = useParams();
  const [cinema, setCinema] = useState(null);
  const [showtimes, setShowtimes] = useState([]);
  const [error, setError] = useState(null);
  // the chosen day is in the address, so going back from a showtime returns to it
  const [params, setParams] = useSearchParams();

  useEffect(() => {
    let cancelled = false;
    Promise.all([cinemaService.get(slug), cinemaService.showtimes(slug)])
      .then(([cinemaData, showtimeData]) => {
        if (cancelled) return;
        setCinema(cinemaData);
        setShowtimes(showtimeData);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [slug]);

  const days = useMemo(() => groupByDay(showtimes), [showtimes]);
  const day = days.find((d) => d.key === params.get("day")) ?? days[0];

  function choose(key) {
    setParams(key === days[0].key ? {} : { day: key }, { replace: true });
  }

  return (
    <div className="page">
      <SiteHeader />

      <main className="page__body">
        <Link to="/" className="back">
          All cinemas
        </Link>

        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        {!cinema && !error && <p className="status">Loading the programme…</p>}

        {cinema && (
          <>
            <h1 className="title">{cinema.name}</h1>

            {days.length === 0 ? (
              <div className="empty">
                <p>{cinema.name} has no showtimes planned yet.</p>
                <Link className="button button--quiet" to="/">
                  See other cinemas
                </Link>
              </div>
            ) : (
              <>
                <div className="days" role="group" aria-label="Day">
                  {days.map((d) => {
                    const [weekday, ...date] = formatDay(d.first).split(" ");
                    const relative = formatDayRelative(d.first);
                    return (
                      <button
                        key={d.key}
                        type="button"
                        className="day"
                        aria-pressed={d.key === day.key}
                        onClick={() => choose(d.key)}
                      >
                        <span className="day__name">{relative === formatDay(d.first) ? weekday : relative}</span>
                        <span className="day__date">{date.join(" ")}</span>
                      </button>
                    );
                  })}
                </div>

                <h2 className="visually-hidden">Showtimes on {formatDay(day.first)}</h2>
                <div className="films">
                  {day.films.map(({ movie, showtimes: filmShowtimes }) => (
                    <article className="film" key={movie.id}>
                      <div className="film__about">
                        <h3>{movie.title}</h3>
                        <p className="film__meta">
                          {movie.release_year}, {formatDuration(movie.duration_minutes)}
                        </p>
                        {movie.description && <p className="film__description">{movie.description}</p>}
                      </div>
                      <ul className="slots" aria-label={`Showtimes of ${movie.title}`}>
                        {filmShowtimes.map((showtime) => (
                          <li key={showtime.id}>
                            <Link to={`/cinemas/${slug}/showtimes/${showtime.id}`} className="slot">
                              <span className="slot__time">{formatTime(showtime.start_time)}</span>
                              <span className="slot__detail">
                                {showtime.hall.name}, {formatPrice(showtime.ticket_price)}
                              </span>
                            </Link>
                          </li>
                        ))}
                      </ul>
                    </article>
                  ))}
                </div>
              </>
            )}
          </>
        )}
      </main>

      <SiteFooter />
    </div>
  );
}

export default CinemaPage;
