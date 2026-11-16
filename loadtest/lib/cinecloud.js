import http from 'k6/http';
import { check } from 'k6';
import exec from 'k6/execution';

// The app, under the name the gateway routes by.
const BASE_URL = __ENV.BASE_URL || 'http://localhost';

// Where k6 runs, that name may lead somewhere else. HOSTS says where to find
// it instead, e.g. {"localhost":"192.168.49.2:32263"} (see run.py).
export const hosts = JSON.parse(__ENV.HOSTS || '{}');

// 409 is an answer, not an error: somebody else was faster.
http.setResponseCallback(http.expectedStatuses({ min: 200, max: 299 }, 409));

const JSON_BODY = { 'Content-Type': 'application/json' };

/**
 * The pages of one cinema. Each scenario has a cinema of its own, so that the
 * bookings of one do not change what the other finds (see README.md).
 */
export function cinema(slug) {
  const api = `${BASE_URL}/api/cinemas/${slug}`;

  /** The seat map once more, see seatMap below. */
  function seats(showtimeId) {
    const res = http.get(`${api}/showtimes/${showtimeId}`, { tags: { name: 'seat stream' } });
    check(res, { 'seat map loaded': (r) => r.status === 200 });
    return res.status === 200 ? res.json().seats : null;
  }

  return {
    /** The cinema's page: the cinema and its upcoming showtimes, side by side. */
    page() {
      const [details, showtimes] = http.batch([
        ['GET', api, null, { tags: { name: 'cinema' } }],
        ['GET', `${api}/showtimes`, null, { tags: { name: 'showtimes' } }],
      ]);
      check(details, { 'cinema loaded': (r) => r.status === 200 });
      check(showtimes, { 'showtimes loaded': (r) => r.status === 200 });
      return showtimes.status === 200 ? showtimes.json() : [];
    },

    /** The showtime page: its details, and the seat map the stream starts with. */
    showtimePage(showtimeId) {
      const [details, snapshot] = http.batch([
        ['GET', `${api}/showtimes/${showtimeId}?seats=false`, null, { tags: { name: 'showtime' } }],
        ['GET', `${api}/showtimes/${showtimeId}`, null, { tags: { name: 'seat stream' } }],
      ]);
      check(details, { 'showtime loaded': (r) => r.status === 200 });
      check(snapshot, { 'seat map loaded': (r) => r.status === 200 });
      return details.status === 200 && snapshot.status === 200 ? snapshot.json() : null;
    },

    seatMap: seats,

    /** Holds the seats; the hold token, or null if somebody was faster (409). */
    hold(showtimeId, seatIds) {
      const res = http.post(
        `${api}/showtimes/${showtimeId}/holds`,
        JSON.stringify({ seat_ids: seatIds }),
        { headers: JSON_BODY, tags: { name: 'hold' } },
      );
      check(res, { 'hold placed or seats taken': (r) => r.status === 201 || r.status === 409 });
      return res.status === 201 ? res.json('hold_token') : null;
    },

    /** Books held seats; true once the booking is confirmed. */
    book(showtimeId, holdToken) {
      // a fresh address per booking; Mailpit catches every confirmation
      const guest = `guest-${exec.vu.idInTest}-${exec.vu.iterationInInstance}@example.com`;
      const res = http.post(
        `${api}/showtimes/${showtimeId}/bookings`,
        JSON.stringify({ hold_token: holdToken, guest_email: guest }),
        { headers: JSON_BODY, tags: { name: 'booking' } },
      );
      return res.status === 201;
    },
  };
}

/**
 * Seats next to each other, as a couple or a family wants them: a random free
 * seat and the free ones to its right in the same row - fewer than wanted
 * if the row runs out. Empty when nothing is free.
 */
export function pickSeats(seats, wanted) {
  const free = seats.filter((seat) => seat.status === 'available');
  if (free.length === 0) return [];
  const freeAt = new Map(free.map((seat) => [`${seat.row_number}:${seat.seat_number}`, seat]));
  const first = free[Math.floor(Math.random() * free.length)];
  const picked = [first.id];
  for (let number = first.seat_number + 1; picked.length < wanted; number++) {
    const next = freeAt.get(`${first.row_number}:${number}`);
    if (!next) break;
    picked.push(next.id);
  }
  return picked;
}
