import { getAccessToken } from './oidc';

const API_BASE_URL = '/api';

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
    const token = await getAccessToken();
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

/* Signing in happens at Keycloak (see oidc.js); the backend only knows which
   cinema an account manages. */
export const authService = {
  /** Cinema of the signed-in account. 401: no valid token, 403: the account
      is not linked to a cinema. */
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
