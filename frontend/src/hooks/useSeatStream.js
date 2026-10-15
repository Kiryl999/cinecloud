import { useEffect, useState } from "react";

import { cinemaService } from "../services/api";

/* The server reports how many seconds a hold has left rather than when it
   ends. Turning that into a deadline on this clock, at the moment it arrives,
   keeps countdowns right even when the visitor's system clock is off. */
export function toSeats(seatStates, receivedAt = Date.now()) {
  return seatStates.map((seat) => ({
    ...seat,
    heldUntil:
      seat.status === "held" ? receivedAt + seat.hold_expires_in * 1000 : null,
  }));
}

/** A hold that has run out counts as free - no event announces the expiry. */
export function effectiveStatus(seat, now) {
  if (seat.status === "held" && seat.heldUntil <= now) return "available";
  return seat.status;
}

function applyChange(seats, change, receivedAt) {
  const affected = new Set(change.seat_ids);
  return seats.map((seat) => {
    if (!affected.has(seat.id)) return seat;
    if (change.event === "held") {
      return { ...seat, status: "held", heldUntil: receivedAt + change.expires_in * 1000 };
    }
    return { ...seat, status: "booked", heldUntil: null };
  });
}

/**
 * Seat states of one showtime, kept current over server-sent events.
 *
 * The server starts every connection with a full snapshot and then sends each
 * change. EventSource reconnects by itself after a dropped connection, and the
 * fresh snapshot then covers whatever happened in between.
 */
export function useSeatStream(slug, showtimeId) {
  const [seats, setSeats] = useState(null);
  const [live, setLive] = useState(false);

  useEffect(() => {
    const source = new EventSource(cinemaService.seatStreamUrl(slug, showtimeId));

    source.addEventListener("snapshot", (event) => {
      setSeats(toSeats(JSON.parse(event.data).seats));
      setLive(true);
    });
    source.addEventListener("seats", (event) => {
      const change = JSON.parse(event.data);
      const receivedAt = Date.now();
      setSeats((current) => (current ? applyChange(current, change, receivedAt) : current));
    });
    source.onerror = () => setLive(false);

    return () => source.close();
  }, [slug, showtimeId]);

  return { seats, live };
}
