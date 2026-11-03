import { useCallback, useEffect, useMemo, useState } from 'react';

import { AuthContext } from './authContext';
import { authService } from '../services/api';
import { completeSignin, userManager } from '../services/oidc';

/* status is deliberately three-valued: "loading" exists so a protected route
   does not bounce the user to the login page while the stored session is
   still being verified. */
const LOADING = 'loading';
const AUTHENTICATED = 'authenticated';
const ANONYMOUS = 'anonymous';

function AuthProvider({ children }) {
  const [admin, setAdmin] = useState(null);
  const [status, setStatus] = useState(LOADING);

  /* Keycloak vouches for the person, the backend for the cinema they manage.
     Name and e-mail come from the ID token, the cinema from /auth/me. */
  const loadAdmin = useCallback(async (user) => {
    try {
      const data = await authService.me();
      setAdmin({ ...data, email: user.profile.email });
      setStatus(AUTHENTICATED);
    } catch (err) {
      // 401: the session is over. On 403 it is kept, so that signing out can
      // tell Keycloak which session to end without asking the user to confirm.
      if (err.status === 401) await userManager.removeUser();
      setAdmin(null);
      setStatus(ANONYMOUS);
      throw err;
    }
  }, []);

  // A stored session proves nothing, its tokens may have run out or the
  // account may have lost its cinema. Ask the backend before trusting it.
  useEffect(() => {
    let cancelled = false;

    userManager.getUser().then((user) => {
      if (cancelled) return;
      if (user) {
        loadAdmin(user).catch(() => {});
      } else {
        // on /admin/callback the sign-in may complete first, so only settle
        // a status nobody has set yet
        setStatus((current) => (current === LOADING ? ANONYMOUS : current));
      }
    });

    return () => {
      cancelled = true;
    };
  }, [loadAdmin]);

  /** Leaves for Keycloak's sign-in page; `from` is where to return after. */
  const login = useCallback(
    (from) => userManager.signinRedirect({ state: { from } }),
    [],
  );

  /** Back from Keycloak: redeem the code, then resolve with `from`. */
  const finishLogin = useCallback(async () => {
    const user = await completeSignin();
    await loadAdmin(user);
    return user.state?.from;
  }, [loadAdmin]);

  // Ends the session at Keycloak too - otherwise the next "Sign in" would
  // come straight back signed in, without asking anyone.
  const logout = useCallback(() => userManager.signoutRedirect(), []);

  const value = useMemo(
    () => ({
      admin,
      status,
      isLoading: status === LOADING,
      isAuthenticated: status === AUTHENTICATED,
      login,
      finishLogin,
      logout,
    }),
    [admin, status, login, finishLogin, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export default AuthProvider;
