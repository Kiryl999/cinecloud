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

/** The API sends decimals as strings, e.g. "12.50". */
export const formatPrice = (value) => priceFormat.format(Number(value));

export function formatDuration(minutes) {
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return hours ? `${hours} h ${rest} min` : `${rest} min`;
}
