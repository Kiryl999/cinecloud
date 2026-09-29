import { useEffect, useState } from 'react';

import { useAuth } from '../hooks/useAuth';
import { hallService, movieService, showtimeService } from '../services/api';
import '../styles/Admin.css';

function useOverview() {
  const [counts, setCounts] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;

    Promise.all([movieService.list(), hallService.list(), showtimeService.list()])
      .then(([movies, halls, showtimes]) => {
        if (cancelled) return;
        setCounts({
          movies: movies.length,
          halls: halls.length,
          showtimes: showtimes.length,
        });
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return { counts, error };
}

function AdminDashboardPage() {
  const { admin, logout } = useAuth();
  const { counts, error } = useOverview();

  return (
    <div className="admin">
      <header className="admin__bar">
        <span className="logo">CineCloud</span>
        <div className="admin__identity">
          <span>{admin?.email}</span>
          <button type="button" onClick={logout}>
            Sign out
          </button>
        </div>
      </header>

      <main className="admin__body">
        <span className="eyebrow">Cinema #{admin?.cinema_id}</span>
        <h1>Dashboard</h1>

        {error && <p className="admin-login__error">{error}</p>}

        <div className="admin__cards">
          <article className="admin__card">
            <span className="admin__count">{counts?.movies ?? '—'}</span>
            <h2>Movies</h2>
          </article>
          <article className="admin__card">
            <span className="admin__count">{counts?.halls ?? '—'}</span>
            <h2>Halls</h2>
          </article>
          <article className="admin__card">
            <span className="admin__count">{counts?.showtimes ?? '—'}</span>
            <h2>Showtimes</h2>
          </article>
        </div>

        <p className="admin-status">
          Managing these is the next step - the API endpoints already exist.
        </p>
      </main>
    </div>
  );
}

export default AdminDashboardPage;
