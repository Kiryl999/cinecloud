import { check, fail } from 'k6';
import { Counter, Gauge } from 'k6/metrics';
import { cinema, pickSeats } from './lib/cinecloud.js';


const premiere = cinema(__ENV.CINEMA || 'loadtest-rush');
const GUESTS = Number(__ENV.GUESTS || 200);

const ATTEMPTS = 20;

const seatsConfirmed = new Counter('seats_confirmed');
const holdsLost = new Counter('holds_lost_to_others');
const rejectedAfterHold = new Counter('bookings_rejected_after_hold');
const guestsWithoutSeats = new Counter('guests_without_seats');
const hallSeats = new Gauge('hall_seats');
const seatsSold = new Gauge('seats_sold');
const seatsStillHeld = new Gauge('seats_still_held');

export const options = {
  scenarios: {
    premiere: {
      executor: 'per-vu-iterations',
      vus: GUESTS,
      iterations: 1,
      maxDuration: '3m',
    },
  },
  thresholds: {
    bookings_rejected_after_hold: ['count==0'],
    seats_still_held: ['value==0'],
    checks: ['rate==1'],
  },
};

export function setup() {
  const showtimes = premiere.page();
  if (showtimes.length === 0) fail(`cinema has no upcoming showtimes - see README.md`);

  const halls = new Map();
  for (const showtime of showtimes) {
    if (!halls.has(showtime.hall.id)) halls.set(showtime.hall.id, []);
    halls.get(showtime.hall.id).push(showtime.id);
  }
  let biggest = null;
  for (const [hallId, ids] of halls) {
    const size = premiere.seatMap(ids[0]).length;
    if (!biggest || size > biggest.size) biggest = { hallId, ids, size };
  }

  for (const id of biggest.ids) {
    const seats = premiere.seatMap(id);
    if (seats.every((seat) => seat.status === 'available')) {
      console.log(`showtime ${id}: ${seats.length} seats, ${GUESTS} guests`);
      return { showtimeId: id };
    }
  }
  fail('every showtime of the biggest hall has been used - see README.md');
}

export default function ({ showtimeId }) {
  const wanted = 1 + Math.floor(Math.random() * 4);
  let seats = premiere.showtimePage(showtimeId)?.seats;

  for (let attempt = 1; seats && attempt <= ATTEMPTS; attempt++) {
    const seatIds = pickSeats(seats, wanted);
    if (seatIds.length === 0) break; // sold out

    const token = premiere.hold(showtimeId, seatIds);
    if (token) {
      if (premiere.book(showtimeId, token)) seatsConfirmed.add(seatIds.length);
      else rejectedAfterHold.add(1);
      return;
    }
    holdsLost.add(1);
    seats = premiere.seatMap(showtimeId);
  }
  guestsWithoutSeats.add(1);
}

export function teardown({ showtimeId }) {
  const seats = premiere.seatMap(showtimeId);
  const count = (status) => seats.filter((seat) => seat.status === status).length;
  hallSeats.add(seats.length);
  seatsSold.add(count('booked'));
  seatsStillHeld.add(count('held'));
  // with more guests than seats, nothing may be left over
  check(seats, { 'showtime sold out': () => GUESTS < seats.length || count('available') === 0 });
}
