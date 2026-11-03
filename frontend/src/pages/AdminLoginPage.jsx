import { useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';

import { useAuth } from '../hooks/useAuth';
import '../styles/Admin.css';

/** Entry to the operator area. The credentials are never entered here: the
    button leads to Keycloak, which signs in with a passkey or a password. */
function AdminLoginPage() {
  const { isAuthenticated, isLoading, login } = useAuth();
  const location = useLocation();

  const [error, setError] = useState(null);
  const [redirecting, setRedirecting] = useState(false);

  // already signed in - no reason to show the page again
  if (!isLoading && isAuthenticated) {
    return <Navigate to="/admin" replace />;
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
        <span className="logo">CineCloud</span>
        <span className="eyebrow">Operator area</span>
        <h1>Sign in</h1>

        <p className="admin-login__hint">
          You will be taken to the CineCloud sign-in page. Use the passkey on
          your device, or your password the first time.
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
          {redirecting ? 'Redirecting…' : 'Sign in'}
        </button>
      </div>
    </div>
  );
}

export default AdminLoginPage;
