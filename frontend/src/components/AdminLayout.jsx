import { NavLink, Outlet, useLocation } from 'react-router-dom';

import { useAuth } from '../hooks/useAuth';
import { useProgrammeLoader } from '../hooks/useProgramme';
import '../styles/Admin.css';

/** Frame of the operator area: who is signed in, the sections, and the
    cinema's programme, shared by all of them (see useProgramme). */
function AdminLayout() {
  const { account, admin, logout } = useAuth();
  // Loaded anew on every change of section: guests keep booking meanwhile,
  // and the seats sold should not stay as they were at sign-in.
  const { pathname } = useLocation();
  const { programme, error, refresh } = useProgrammeLoader(pathname);

  return (
    <div className="admin">
      <header className="admin__bar">
        <span className="logo">CineCloud</span>
        <div className="admin__identity">
          <span>Signed in as {account?.email}</span>
          <button type="button" onClick={logout}>
            Sign out
          </button>
        </div>
      </header>

      <nav className="admin__nav" aria-label="Operator area">
        <NavLink to="/admin" end>
          Overview
        </NavLink>
        <NavLink to="/admin/showtimes">Showtimes</NavLink>
        <NavLink to="/admin/bookings">Bookings</NavLink>
        <NavLink to="/admin/movies">Movies</NavLink>
        <NavLink to="/admin/halls">Halls</NavLink>
      </nav>

      <main className="admin__body">
        <span className="eyebrow">{admin?.cinema?.name}</span>

        {error && (
          <p className="admin-login__error" role="alert">
            {error}
          </p>
        )}
        {programme ? (
          <Outlet context={{ programme, refresh }} />
        ) : (
          !error && <p className="admin-status">Loading your programme…</p>
        )}
      </main>
    </div>
  );
}

export default AdminLayout;
