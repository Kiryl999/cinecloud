import { Navigate, useLocation } from 'react-router-dom';

import { useAuth } from '../hooks/useAuth';

/** Gate for the operator area. Renders nothing decisive while the stored token
    is still being verified, so a reload does not flash the login page. */
function ProtectedRoute({ children }) {
  const { isLoading, isAuthenticated, isUnlinked } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return <p className="admin-status">Checking your session…</p>;
  }

  // signed in, but there is no cinema to manage yet
  if (isUnlinked) {
    return <Navigate to="/admin/setup" replace />;
  }

  if (!isAuthenticated) {
    // remember where the user wanted to go, so login can send them back
    return <Navigate to="/admin/login" replace state={{ from: location }} />;
  }

  return children;
}

export default ProtectedRoute;
