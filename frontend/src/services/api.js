const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const TOKEN_KEY = 'cinecloud.admin.token';

/* Token storage.

   localStorage keeps the admin logged in across reloads, but it is readable by
   any script on the page - an XSS bug would leak the token. The alternative is
   an httpOnly cookie, which the browser never exposes to JavaScript, but that
   requires the backend to set cookies and to defend against CSRF. As long as
   the API authenticates with Bearer tokens, this is the matching client side. */
export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

/** FastAPI reports failures as {"detail": "..."} - fall back if it does not. */
async function errorMessage(response, fallback) {
  try {
    const body = await response.json();
    if (typeof body.detail === 'string') return body.detail;
  } catch {
    // response had no JSON body
  }
  return fallback;
}

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function request(path, { method = 'GET', body, auth = false } = {}) {
  const headers = {};
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (auth) {
    const token = getToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (!response.ok) {
    throw new ApiError(
      await errorMessage(response, `Request failed (${response.status})`),
      response.status,
    );
  }

  return response.status === 204 ? null : response.json();
}

export const authService = {
  /* The backend uses OAuth2PasswordRequestForm, so the credentials go out as
     application/x-www-form-urlencoded - not JSON - and the field is called
     `username` even though it carries an e-mail address. */
  login: async (email, password) => {
    const response = await fetch(`${API_BASE_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ username: email, password }),
    });

    if (!response.ok) {
      throw new ApiError(
        await errorMessage(response, 'Login failed'),
        response.status,
      );
    }

    const { access_token: accessToken } = await response.json();
    setToken(accessToken);
    return accessToken;
  },

  /** Current admin, derived from the stored token. 401 means it is gone or expired. */
  me: () => request('/auth/me', { auth: true }),
};

export const cinemaService = {
  // all cinemas from backend
  getAll: () => request('/cinemas/'),
  get: (slug) => request(`/cinemas/${encodeURIComponent(slug)}`),
  /** Upcoming showtimes of one cinema, each with its movie and hall. */
  showtimes: (slug) => request(`/cinemas/${encodeURIComponent(slug)}/showtimes`),
  /** One showtime including the current state of every seat. */
  showtime: (slug, showtimeId) =>
    request(`/cinemas/${encodeURIComponent(slug)}/showtimes/${showtimeId}`),
  /** Live seat map as server-sent events - opened with EventSource, not fetch. */
  seatStreamUrl: (slug, showtimeId) =>
    `${API_BASE_URL}/cinemas/${encodeURIComponent(slug)}/showtimes/${showtimeId}/seats/stream`,
};

/* Guest booking. No token: the hold token returned when reserving is the
   guest's only proof that the held seats are theirs. */
export const bookingService = {
  hold: (slug, showtimeId, seatIds) =>
    request(`/cinemas/${encodeURIComponent(slug)}/showtimes/${showtimeId}/holds`, {
      method: 'POST',
      body: { seat_ids: seatIds },
    }),
  book: (slug, showtimeId, holdToken, guestEmail) =>
    request(`/cinemas/${encodeURIComponent(slug)}/showtimes/${showtimeId}/bookings`, {
      method: 'POST',
      body: { hold_token: holdToken, guest_email: guestEmail },
    }),
};

export const movieService = {
  list: () => request('/movies/', { auth: true }),
};

export const hallService = {
  list: () => request('/halls/', { auth: true }),
};

export const showtimeService = {
  list: () => request('/showtimes/', { auth: true }),
};
