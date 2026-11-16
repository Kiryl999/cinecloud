import { sleep } from 'k6';
import { cinema, hosts, pickSeats } from './lib/cinecloud.js';

const evening = cinema(__ENV.CINEMA || 'loadtest');

const PEAK = Number(__ENV.PEAK || 30);

const PEAK_MINUTES = Number(__ENV.PEAK_MINUTES || 5);

const HOLD_SHARE = 0.3;
const BOOK_SHARE = 0.5;

export const options = {
  hosts,
  scenarios: {
    evening: {
      executor: 'ramping-arrival-rate',
      timeUnit: '1s',
      startRate: 1,
      stages: [

        { duration: '1m', target: Math.ceil(PEAK / 4) },
        { duration: '2m', target: Math.ceil(PEAK / 4) },

        { duration: '6m', target: PEAK },
        { duration: `${PEAK_MINUTES}m`, target: PEAK },
        { duration: '1m', target: 0 },
      ],
      preAllocatedVUs: PEAK * 10,
      maxVUs: PEAK * 40,
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    'http_req_duration{expected_response:true}': ['p(95)<1000'],
  },
};

export function setup() {
  const showtimes = evening.page();
  if (showtimes.length === 0) throw new Error('cinema has no upcoming showtimes - see README.md');
  return { showtimeIds: showtimes.map((showtime) => showtime.id) };
}

export default function ({ showtimeIds }) {
  evening.page();
  sleep(2 + Math.random() * 4); // reading the programme

  const showtimeId = showtimeIds[Math.floor(Math.random() * showtimeIds.length)];
  const showtime = evening.showtimePage(showtimeId);
  if (!showtime || Math.random() >= HOLD_SHARE) return;
  sleep(3 + Math.random() * 5); // choosing seats

  const seatIds = pickSeats(showtime.seats, 1 + Math.floor(Math.random() * 4));
  if (seatIds.length === 0) return; // sold out
  const token = evening.hold(showtimeId, seatIds);
  // the others leave without booking; their hold runs out after ten minutes
  if (!token || Math.random() >= BOOK_SHARE) return;
  sleep(10 + Math.random() * 10); // entering the e-mail address, paying

  evening.book(showtimeId, token);
}
