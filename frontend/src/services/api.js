import { getAccessToken } from './oidc';

const API_BASE_URL = '/api';

/** FastAPI reports failures as {"detail": "..."}, and a request that fails
    validation (422) with a list of them - fall back if neither. */
async function errorMessage(response, fallback) {
  try {
    const body = await response.json();
    if (typeof body.detail === 'string') return body.detail;
    if (Array.isArray(body.detail) && body.detail[0]?.msg) return body.detail[0].msg;
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
  /** Opens a cinema managed by the signed-in account, which must manage none
      yet. `cinema` is {name, slug, demo_programme}. */
  open: (cinema) => request('/cinemas/', { method: 'POST', body: cinema, auth: true }),
  get: (slug) => request(`/cinemas/${encodeURIComponent(slug)}`),
  /** Upcoming showtimes of one cinema, each with its movie and hall. */
  showtimes: (slug) => request(`/cinemas/${encodeURIComponent(slug)}/showtimes`),
  /** One showtime including the current state of every seat - unless `seats`
      is false, for a page that takes the seats from the stream. */
  showtime: (slug, showtimeId, { seats = true } = {}) =>
    request(
      `/cinemas/${encodeURIComponent(slug)}/showtimes/${showtimeId}${seats ? '' : '?seats=false'}`,
    ),
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

/** The signed-in admin's own movies, halls or showtimes. The backend takes
    the cinema from the token, so no request names it. */
function adminResource(path) {
  return {
    list: () => request(`${path}/`, { auth: true }),
    create: (values) => request(`${path}/`, { method: 'POST', body: values, auth: true }),
    /** Changes only the fields in `changes`. */
    update: (id, changes) =>
      request(`${path}/${id}`, { method: 'PATCH', body: changes, auth: true }),
    remove: (id) => request(`${path}/${id}`, { method: 'DELETE', auth: true }),
  };
}

export const movieService = adminResource('/movies');

/** Halls are created with `rows` and `seats_per_row`, which then stay fixed:
    only the name can change. */
export const hallService = adminResource('/halls');

/** A showtime stays in its hall, so `hall_id` can only be set on create.
    The list counts each showtime's `seats_sold`. */
export const showtimeService = {
  ...adminResource('/showtimes'),
  /** Every seat with its state - booked, held or available - also for a
      showtime that has started. */
  seats: (id) => request(`/showtimes/${id}/seats`, { auth: true }),
};

/** The cinema's side of the guests' bookings, newest first. `q` is a
    booking reference or part of an e-mail address. */
export const salesService = {
  bookings: ({ showtimeId, q, limit } = {}) => {
    const params = new URLSearchParams();
    if (showtimeId !== undefined) params.set('showtime_id', showtimeId);
    if (q) params.set('q', q);
    if (limit !== undefined) params.set('limit', limit);
    return request(`/bookings/?${params}`, { auth: true });
  },
};
