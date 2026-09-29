import { useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';

import { useAuth } from '../hooks/useAuth';
import '../styles/Admin.css';

function AdminLoginPage() {
  const { isAuthenticated, isLoading, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  // already signed in - no reason to show the form again
  if (!isLoading && isAuthenticated) {
    return <Navigate to="/admin" replace />;
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      await login(email, password);
      // back to wherever ProtectedRoute intercepted, otherwise the dashboard
      navigate(location.state?.from?.pathname ?? '/admin', { replace: true });
    } catch (err) {
      setError(err.message);
      setSubmitting(false);
    }
  }

  return (
    <div className="admin-login">
      <form className="admin-login__card" onSubmit={handleSubmit}>
        <span className="logo">CineCloud</span>
        <span className="eyebrow">Operator area</span>
        <h1>Sign in</h1>

        <label htmlFor="email">E-mail</label>
        <input
          id="email"
          type="email"
          value={email}
          autoComplete="username"
          required
          onChange={(event) => setEmail(event.target.value)}
        />

        <label htmlFor="password">Password</label>
        <input
          id="password"
          type="password"
          value={password}
          autoComplete="current-password"
          required
          onChange={(event) => setPassword(event.target.value)}
        />

        {/* the backend answers with the same message for unknown e-mail and
            wrong password, so this never reveals whether an account exists */}
        {error && (
          <p className="admin-login__error" role="alert">
            {error}
          </p>
        )}

        <button type="submit" className="cta" disabled={submitting}>
          {submitting ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </div>
  );
}

export default AdminLoginPage;
