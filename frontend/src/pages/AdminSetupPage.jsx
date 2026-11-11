import { useState } from 'react';
import { Navigate } from 'react-router-dom';

import { useAuth } from '../hooks/useAuth';
import { cinemaService } from '../services/api';
import '../styles/Admin.css';

// what the backend accepts as an address, see CinemaCreate in
// backend/app/schemas/cinema.py
const SLUG_PATTERN = '[a-z0-9]+(-[a-z0-9]+)*';
const SLUG_MAX_LENGTH = 60;

/** Suggests an address for a name: "Kino Ölberg 2" becomes "kino-oelberg-2". */
function suggestSlug(name) {
  return (
    name
      .toLowerCase()
      .replace(/ä/g, 'ae')
      .replace(/ö/g, 'oe')
      .replace(/ü/g, 'ue')
      .replace(/ß/g, 'ss')
      // other accents: "é" splits into "e" and a mark, and the mark goes
      .normalize('NFD')
      .replace(/[̀-ͯ]/g, '')
      .replace(/[^a-z0-9]+/g, '-')
      .slice(0, SLUG_MAX_LENGTH)
      .replace(/^-+|-+$/g, '')
  );
}

/** Where an account that has just registered opens its cinema. Whoever
    opens it, manages it. */
function AdminSetupPage() {
  const { account, isLoading, isAuthenticated, isUnlinked, reload, logout } = useAuth();

  const [name, setName] = useState('');
  // null while the address follows the name, set once it is edited by hand
  const [customSlug, setCustomSlug] = useState(null);
  const [demoProgramme, setDemoProgramme] = useState(false);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);

  if (isLoading) {
    return <p className="admin-status">Checking your session…</p>;
  }
  // also where the page goes once reload() below has found the new cinema
  if (isAuthenticated) {
    return <Navigate to="/admin" replace />;
  }
  if (!isUnlinked) {
    return <Navigate to="/admin/login" replace />;
  }

  const slug = customSlug ?? suggestSlug(name);

  async function handleSubmit(event) {
    event.preventDefault();
    setError(null);
    setSaving(true);

    try {
      await cinemaService.open({ name, slug, demo_programme: demoProgramme });
      await reload();
    } catch (err) {
      setError(err.message);
      setSaving(false);
    }
  }

  return (
    <div className="admin-login">
      <div className="admin-login__card admin-login__card--wide">
        <span className="logo">CineCloud</span>

        <p className="admin-setup__account">
          <span>
            Signed in as <strong>{account?.email}</strong>
          </span>
          <button type="button" className="admin-setup__link" onClick={logout}>
            Sign out
          </button>
        </p>

        <span className="eyebrow">Welcome</span>
        <h1>Open your cinema</h1>

        <form className="admin-setup__form" onSubmit={handleSubmit}>
          <label htmlFor="cinema-name">Name</label>
          <input
            id="cinema-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Cineplex Bonn"
            maxLength={100}
            required
          />

          <label htmlFor="cinema-slug">Address</label>
          <div className="admin-setup__address">
            <span>{window.location.host}/cinemas/</span>
            <input
              id="cinema-slug"
              value={slug}
              onChange={(event) => setCustomSlug(event.target.value.toLowerCase())}
              minLength={2}
              maxLength={SLUG_MAX_LENGTH}
              pattern={SLUG_PATTERN}
              title="Lower-case letters and digits, words joined by single hyphens"
              required
            />
          </div>

          <label className="admin-setup__check">
            <input
              type="checkbox"
              checked={demoProgramme}
              onChange={(event) => setDemoProgramme(event.target.checked)}
            />
            Start with a demo programme: three movies, two halls and a week of
            showtimes
          </label>

          {error && (
            <p className="admin-login__error" role="alert">
              {error}
            </p>
          )}

          <button type="submit" className="cta" disabled={saving}>
            {saving ? 'Opening…' : 'Open cinema'}
          </button>
        </form>

        <p className="admin-setup__note">
          Joining a cinema that is open already? The platform operator links
          your account to it, by this ID: <code>{account?.id}</code>
        </p>
      </div>
    </div>
  );
}

export default AdminSetupPage;
