import { useState } from 'react';
import { Link, Navigate, useLocation } from 'react-router-dom';

import Logo from '../components/Logo';

import { useAuth } from '../hooks/useAuth';
import '../styles/Admin.css';

/** Entry to the operator area. Nothing is entered here: the button leads to
    Keycloak, which signs in with a passkey and lets new admins register. */
function AdminLoginPage() {
  const { isAuthenticated, isUnlinked, isLoading, login } = useAuth();
  const location = useLocation();

  const [error, setError] = useState(null);
  const [redirecting, setRedirecting] = useState(false);

  // already signed in - no reason to show the page again
  if (!isLoading && isAuthenticated) {
    return <Navigate to="/admin" replace />;
  }
  if (!isLoading && isUnlinked) {
    return <Navigate to="/admin/setup" replace />;
  }

  async function handleSignIn() {
    setError(null);
    setRedirecting(true);

    try {
      // back to wherever ProtectedRoute intercepted, otherwise the dashboard
      await login(location.state?.from?.pathname ?? '/admin');
    } catch {
      // the browser stays here only if Keycloak could not be reached
      setError('The sign-in service is not reachable. Please try again later.');
      setRedirecting(false);
    }
  }

  return (
    <div className="admin-login">
      <div className="admin-login__card">
        <Link to="/" className="logo">
          <Logo />
        </Link>
        <h1>Run a cinema on CineCloud</h1>

        <p className="admin-login__hint">
          This is a demo: anyone can open a cinema of their own, plan its
          programme and watch the bookings come in. Sign in with a passkey, or
          register if you are new; there is no password.
        </p>

        {error && (
          <p className="admin-login__error" role="alert">
            {error}
          </p>
        )}

        <button
          type="button"
          className="cta"
          disabled={redirecting}
          onClick={handleSignIn}
        >
          {redirecting ? 'Redirecting…' : 'Sign in or register'}
        </button>

        <Link to="/" className="admin-login__back">
          Back to the cinemas
        </Link>
      </div>
    </div>
  );
}

export default AdminLoginPage;
