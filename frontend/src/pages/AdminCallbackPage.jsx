import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { useAuth } from '../hooks/useAuth';
import '../styles/Admin.css';

/** Where Keycloak sends the browser back to, with a one-time code in the URL. */
function AdminCallbackPage() {
  const { finishLogin, logout } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState(null);

  useEffect(() => {
    finishLogin()
      // replace: the back button must not return to an already redeemed code
      .then((from) => navigate(from ?? '/admin', { replace: true }))
      .catch((err) => setError(err.message));
  }, [finishLogin, navigate]);

  if (!error) {
    return <p className="admin-status">Signing you in…</p>;
  }

  /* An account without a cinema is no error, it goes on to /admin/setup.
     This is the rest: Keycloak or the backend unreachable, or a code that
     was redeemed already. Signing out ends the session at Keycloak, so the
     next attempt starts from scratch. */
  return (
    <div className="admin-login">
      <div className="admin-login__card">
        <span className="logo">CineCloud</span>
        <h1>Sign-in failed</h1>
        <p className="admin-login__error" role="alert">
          {error}
        </p>
        <button type="button" className="cta" onClick={logout}>
          Sign out
        </button>
      </div>
    </div>
  );
}

export default AdminCallbackPage;
