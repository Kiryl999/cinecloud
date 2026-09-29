import { useCallback, useEffect, useMemo, useState } from 'react';

import { AuthContext } from './authContext';
import { authService, clearToken, getToken } from '../services/api';

/* status is deliberately three-valued: "loading" exists so a protected route
   does not bounce the user to the login page while the stored token is still
   being verified. */
const LOADING = 'loading';
const AUTHENTICATED = 'authenticated';
const ANONYMOUS = 'anonymous';

function AuthProvider({ children }) {
  const [admin, setAdmin] = useState(null);
  const [status, setStatus] = useState(getToken() ? LOADING : ANONYMOUS);

  // A stored token proves nothing, it may be expired or signed with a rotated
  // secret. Ask the backend who it belongs to before trusting it.
  useEffect(() => {
    if (!getToken()) return;

    let cancelled = false;
    authService
      .me()
      .then((data) => {
        if (cancelled) return;
        setAdmin(data);
        setStatus(AUTHENTICATED);
      })
      .catch(() => {
        if (cancelled) return;
        clearToken();
        setAdmin(null);
        setStatus(ANONYMOUS);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (email, password) => {
    await authService.login(email, password);
    const data = await authService.me();
    setAdmin(data);
    setStatus(AUTHENTICATED);
    return data;
  }, []);

  const logout = useCallback(() => {
    // The JWT stays valid until it expires. The backend has no denylist yet
    // so this only forgets the token on this device.
    clearToken();
    setAdmin(null);
    setStatus(ANONYMOUS);
  }, []);

  const value = useMemo(
    () => ({
      admin,
      status,
      isLoading: status === LOADING,
      isAuthenticated: status === AUTHENTICATED,
      login,
      logout,
    }),
    [admin, status, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export default AuthProvider;
