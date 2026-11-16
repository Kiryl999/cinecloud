import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import SiteFooter, { SOURCE_URL } from "../components/SiteFooter";
import SiteHeader from "../components/SiteHeader";
import { cinemaService } from "../services/api";
import { formatDayRelative, formatTime } from "../utils/format";
import "../styles/Public.css";

// how many of a cinema's next showtimes the start page offers directly
const NEXT_SHOWTIMES = 4;

/** The start page: what CineCloud is, and every cinema with its next showtimes. */
function CinemaSelectionPage() {
  const [cinemas, setCinemas] = useState(null);
  // slug -> upcoming showtimes; a cinema whose programme failed to load is left out
  const [programmes, setProgrammes] = useState({});
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    cinemaService
      .getAll()
      .then((found) => {
        if (cancelled) return;
        setCinemas(found);
        for (const cinema of found) {
          cinemaService
            .showtimes(cinema.slug)
            .then((showtimes) => {
              if (!cancelled) setProgrammes((current) => ({ ...current, [cinema.slug]: showtimes }));
            })
            .catch(() => {});
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="page">
      <SiteHeader />

      <section className="hero">
        <div className="hero__inner">
          <h1>Pick a cinema, then your seats.</h1>
          <p>
            CineCloud is an open-source demo of a booking platform for cinemas,
            built as a portfolio project. Book real seats on a live seat map;
            payment is simulated, so nothing is charged.
          </p>
          <a className="hero__source" href={SOURCE_URL}>
            See how it is built on GitHub
          </a>
        </div>
      </section>

      <main className="page__body" id="cinemas">
        <h2 className="section-title">
          Cinemas
          {cinemas && cinemas.length > 0 && <span className="section-title__count">{cinemas.length}</span>}
        </h2>

        {error && (
          <p className="error" role="alert">
            The cinemas could not be loaded: {error}
          </p>
        )}
        {!cinemas && !error && <p className="status">Loading cinemas…</p>}

        {cinemas?.length === 0 && (
          <div className="empty">
            <p>No cinema has opened yet.</p>
            <Link className="button" to="/admin">
              Open the first one
            </Link>
          </div>
        )}

        {cinemas?.length > 0 && (
          <ul className="cinemas">
            {cinemas.map((cinema) => (
              <CinemaEntry key={cinema.id} cinema={cinema} showtimes={programmes[cinema.slug]} />
            ))}
          </ul>
        )}
      </main>

      <SiteFooter />
    </div>
  );
}

function CinemaEntry({ cinema, showtimes }) {
  const programme = `/cinemas/${cinema.slug}`;
  return (
    <li className="cinema">
      <h3 className="cinema__name">
        <Link to={programme}>{cinema.name}</Link>
      </h3>

      {showtimes === undefined ? (
        <p className="status">Loading showtimes…</p>
      ) : showtimes.length === 0 ? (
        <p className="status">No showtimes planned yet.</p>
      ) : (
        <>
          <ul className="next-showtimes" aria-label={`Next showtimes at ${cinema.name}`}>
            {showtimes.slice(0, NEXT_SHOWTIMES).map((showtime) => (
              <li key={showtime.id}>
                <Link className="next-showtime" to={`${programme}/showtimes/${showtime.id}`}>
                  <span className="next-showtime__when">
                    {formatDayRelative(showtime.start_time)} {formatTime(showtime.start_time)}
                  </span>
                  <span className="next-showtime__title">{showtime.movie.title}</span>
                </Link>
              </li>
            ))}
          </ul>
          <Link className="cinema__all" to={programme}>
            Full programme, {showtimes.length} {showtimes.length === 1 ? "showtime" : "showtimes"}
          </Link>
        </>
      )}
    </li>
  );
}

export default CinemaSelectionPage;
