import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import SiteHeader from "../components/SiteHeader";
import { cinemaService } from "../services/api";
import "../styles/Public.css";

/** The visitor landing page: every cinema on the platform, each a way into its programme. */
function CinemaSelectionPage() {
  const [cinemas, setCinemas] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    cinemaService
      .getAll()
      .then((data) => setCinemas(data))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="page">
      <SiteHeader />

      <main className="page__body">
        <span className="page__eyebrow">Now showing</span>
        <h1>Choose your cinema</h1>

        {loading && <p className="page__status">Loading cinemas…</p>}
        {error && <p className="page__error">{error}</p>}
        {!loading && !error && cinemas.length === 0 && (
          <p className="page__status">No cinemas yet.</p>
        )}

        <ul className="cinema-list">
          {cinemas.map((cinema) => (
            <li key={cinema.id}>
              <Link to={`/cinemas/${cinema.slug}`} className="cinema-card">
                <span className="cinema-card__name">{cinema.name}</span>
                <span className="cinema-card__action">See programme →</span>
              </Link>
            </li>
          ))}
        </ul>
      </main>
    </div>
  );
}

export default CinemaSelectionPage;
