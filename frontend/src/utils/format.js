// All cinemas on the platform are in Germany. Times are shown in the cinema's
// time zone rather than the visitor's, so a showtime reads the same wherever
// someone opens the page.
const CINEMA_TIME_ZONE = "Europe/Berlin";

const dayFormat = new Intl.DateTimeFormat("en-GB", {
  timeZone: CINEMA_TIME_ZONE,
  weekday: "short",
  day: "numeric",
  month: "short",
});

const timeFormat = new Intl.DateTimeFormat("en-GB", {
  timeZone: CINEMA_TIME_ZONE,
  hour: "2-digit",
  minute: "2-digit",
});

// en-CA formats as YYYY-MM-DD, which makes a stable key for grouping by day
const dayKeyFormat = new Intl.DateTimeFormat("en-CA", {
  timeZone: CINEMA_TIME_ZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

const priceFormat = new Intl.NumberFormat("en-GB", {
  style: "currency",
  currency: "EUR",
});

export const formatDay = (iso) => dayFormat.format(new Date(iso));

export const formatTime = (iso) => timeFormat.format(new Date(iso));

export const dayKey = (iso) => dayKeyFormat.format(new Date(iso));

const DAY_MS = 24 * 60 * 60 * 1000;

/** "Today", "Tomorrow" or the date, judged by the cinema's calendar. */
export function formatDayRelative(iso, now = Date.now()) {
  const key = dayKey(iso);
  if (key === dayKey(now)) return "Today";
  if (key === dayKey(now + DAY_MS)) return "Tomorrow";
  return formatDay(iso);
}

/** The API sends decimals as strings, e.g. "12.50". */
export const formatPrice = (value) => priceFormat.format(Number(value));

export function formatDuration(minutes) {
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return hours ? `${hours} h ${rest} min` : `${rest} min`;
}

// The parts of the cinema's wall clock, for the datetime inputs below
const wallClockFormat = new Intl.DateTimeFormat("en-GB", {
  timeZone: CINEMA_TIME_ZONE,
  hourCycle: "h23",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
});

function wallClock(ms) {
  const parts = Object.fromEntries(
    wallClockFormat.formatToParts(new Date(ms)).map(({ type, value }) => [type, value]),
  );
  return { ...parts, ms: Date.UTC(parts.year, parts.month - 1, parts.day, parts.hour, parts.minute) };
}

/** How far the cinema's clock is ahead of UTC at `ms`, in milliseconds. */
const offsetAt = (ms) => wallClock(ms).ms - Math.floor(ms / 60000) * 60000;

/** A time from the API as the cinema's clock shows it, in the format of
    <input type="datetime-local">: "2026-11-14T20:00". */
export function toDateTimeInput(iso) {
  const { year, month, day, hour, minute } = wallClock(new Date(iso).getTime());
  return `${year}-${month}-${day}T${hour}:${minute}`;
}

/** The reverse: the moment the cinema's clock shows `value`, as ISO 8601 in
    UTC, which the API accepts. The browser's own time zone plays no part, so
    20:00 means 20:00 in the cinema even for an admin abroad. */
export function fromDateTimeInput(value) {
  const [year, month, day, hour, minute] = value.split(/[-T:]/).map(Number);
  const asIfUtc = Date.UTC(year, month - 1, day, hour, minute);
  // the offset is looked up twice: near a daylight saving change, the one at
  // `asIfUtc` can differ from the one at the moment it points to
  const guess = asIfUtc - offsetAt(asIfUtc);
  return new Date(asIfUtc - offsetAt(guess)).toISOString();
}

/** Remaining time as m:ss, e.g. 9:05. */
export function formatCountdown(ms) {
  const seconds = Math.max(0, Math.ceil(ms / 1000));
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

export const seatLabel = (seat) => `Row ${seat.row_number}, seat ${seat.seat_number}`;

/** Several seats, one group per row: "Row 2: 11; row 4: 4, 5, 7". */
export function seatsByRow(seats) {
  const rows = new Map();
  const ordered = [...seats].sort(
    (a, b) => a.row_number - b.row_number || a.seat_number - b.seat_number,
  );
  for (const seat of ordered) {
    if (!rows.has(seat.row_number)) rows.set(seat.row_number, []);
    rows.get(seat.row_number).push(seat.seat_number);
  }
  return [...rows]
    .map(([row, numbers], index) => `${index ? "row" : "Row"} ${row}: ${numbers.join(", ")}`)
    .join("; ");
}
