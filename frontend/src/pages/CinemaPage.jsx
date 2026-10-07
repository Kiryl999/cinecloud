import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import SiteHeader from "../components/SiteHeader";
import { cinemaService } from "../services/api";
import { dayKey, formatDay, formatDuration, formatTime } from "../utils/format";
import "../styles/Public.css";

/** Film by film, day by day. Films are ordered by their next showtime. */
function groupByFilm(showtimes) {
  const films = new Map();
  for (const showtime of showtimes) {
    if (!films.has(showtime.movie.id)) {
      films.set(showtime.movie.id, { movie: showtime.movie, days: new Map() });
    }
    const { days } = films.get(showtime.movie.id);
    const key = dayKey(showtime.start_time);
    if (!days.has(key)) days.set(key, []);
    days.get(key).push(showtime);
  }
  return [...films.values()].map(({ movie, days }) => ({
    movie,
    days: [...days.values()],
  }));
}

function CinemaPage() {
  const { slug } = useParams();
  const [cinema, setCinema] = useState(null);
  const [showtimes, setShowtimes] = useState([]);
  const [error, setError] = useState(null);

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

  const films = useMemo(() => groupByFilm(showtimes), [showtimes]);

  return (
    <div className="page">
      <SiteHeader />

      <main className="page__body">
        <Link to="/" className="page__back">
          ← All cinemas
        </Link>

        {error && <p className="page__error">{error}</p>}
        {!cinema && !error && <p className="page__status">Loading programme…</p>}

        {cinema && (
          <>
            <span className="page__eyebrow">Programme</span>
            <h1>{cinema.name}</h1>

            {films.length === 0 && (
              <p className="page__status">No upcoming showtimes.</p>
            )}

            {films.map(({ movie, days }) => (
              <article className="film" key={movie.id}>
                <h2>{movie.title}</h2>
                <p className="film__meta">
                  {movie.release_year} · {formatDuration(movie.duration_minutes)}
                </p>
                {movie.description && (
                  <p className="film__description">{movie.description}</p>
                )}

                {days.map((dayShowtimes) => (
                  <div className="film__day" key={dayKey(dayShowtimes[0].start_time)}>
                    <span className="film__date">
                      {formatDay(dayShowtimes[0].start_time)}
                    </span>
                    <ul className="slots">
                      {dayShowtimes.map((showtime) => (
                        <li key={showtime.id}>
                          <Link
                            to={`/cinemas/${slug}/showtimes/${showtime.id}`}
                            className="slot"
                          >
                            <span className="slot__time">
                              {formatTime(showtime.start_time)}
                            </span>
                            <span className="slot__hall">{showtime.hall.name}</span>
                          </Link>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </article>
            ))}
          </>
        )}
      </main>
    </div>
  );
}

export default CinemaPage;
