import { useCallback, useEffect, useMemo, useState } from 'react';

import { AuthContext } from './authContext';
import { authService } from '../services/api';
import { completeSignin, userManager } from '../services/oidc';

/* "loading" exists so a protected route does not bounce the user to the login
   page while the stored session is still being verified. "unlinked" is an
   account signed in at Keycloak that manages no cinema yet - typically one
   that has just registered, and opens its cinema next. */
const LOADING = 'loading';
const AUTHENTICATED = 'authenticated';
const UNLINKED = 'unlinked';
const ANONYMOUS = 'anonymous';

function AuthProvider({ children }) {
  // the Keycloak account, from the ID token: who is signed in
  const [account, setAccount] = useState(null);
  // the backend's record of it: which cinema that account manages
  const [admin, setAdmin] = useState(null);
  const [status, setStatus] = useState(LOADING);

  const loadAdmin = useCallback(async (user) => {
    setAccount({ id: user.profile.sub, email: user.profile.email });
    try {
      setAdmin(await authService.me());
      setStatus(AUTHENTICATED);
    } catch (err) {
      setAdmin(null);
      // Signed in, but no cinema yet. The session is kept: the account opens
      // its cinema with it, or signs out without Keycloak asking to confirm.
      if (err.status === 403) {
        setStatus(UNLINKED);
        return;
      }
      // 401: the session is over
      if (err.status === 401) await userManager.removeUser();
      setAccount(null);
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

  /** Asks the backend again, e.g. once the account has opened its cinema. */
  const reload = useCallback(async () => {
    const user = await userManager.getUser();
    if (user) await loadAdmin(user);
  }, [loadAdmin]);

  // Ends the session at Keycloak too - otherwise the next "Sign in" would
  // come straight back signed in, without asking anyone.
  const logout = useCallback(() => userManager.signoutRedirect(), []);

  const value = useMemo(
    () => ({
      account,
      admin,
      status,
      isLoading: status === LOADING,
      isAuthenticated: status === AUTHENTICATED,
      isUnlinked: status === UNLINKED,
      login,
      finishLogin,
      reload,
      logout,
    }),
    [account, admin, status, login, finishLogin, reload, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export default AuthProvider;
