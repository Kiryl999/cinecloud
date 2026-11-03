import { UserManager } from 'oidc-client-ts';

/* Keycloak signs the operators in. In the cluster the gateway serves it under
   /auth on the app's own origin; `npm run dev` has no gateway, so
   .env.development points at a Keycloak running on its own port. */
const authority =
  import.meta.env.VITE_OIDC_AUTHORITY ??
  `${window.location.origin}/auth/realms/cinecloud`;

/* Authorization code flow with PKCE: the browser gets a one-time code from
   Keycloak and redeems it together with a secret it generated itself, so a
   code intercepted on the way back is useless.

   The tokens end up in sessionStorage, which any script on the page can read -
   an XSS bug would leak them, as it would have leaked the token in
   localStorage before. Keeping them out of reach entirely would take a backend
   that holds the tokens and gives the browser an httpOnly cookie instead. */
export const userManager = new UserManager({
  authority,
  client_id: 'cinecloud-web',
  redirect_uri: `${window.location.origin}/admin/callback`,
  post_logout_redirect_uri: `${window.location.origin}/`,
  scope: 'openid email',
  // renews the access token with the refresh token shortly before it expires
  automaticSilentRenew: true,
});

/** The current access token, renewed first if it has expired - e.g. after the
    tab was reloaded later than the token lives. Null if the session is over. */
export async function getAccessToken() {
  let user = await userManager.getUser();
  if (user?.expired) {
    user = await userManager.signinSilent().catch(() => null);
  }
  return user?.access_token ?? null;
}

/* The code in the callback URL can be redeemed only once, but StrictMode runs
   effects twice in development. Both runs share one attempt; a new sign-in
   loads the page anew and starts with a fresh module. */
let callback = null;

export function completeSignin() {
  callback ??= userManager.signinRedirectCallback();
  return callback;
}
