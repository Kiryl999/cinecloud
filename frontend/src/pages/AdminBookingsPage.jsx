import { useEffect, useState } from 'react';

import AdminBookingList from '../components/AdminBookingList';
import { useProgramme } from '../hooks/useProgramme';
import { salesService } from '../services/api';

const LIMIT = 100;
// search once typing pauses, not on every key
const SEARCH_DELAY_MS = 300;

function AdminBookingsPage() {
  const { programme } = useProgramme();
  const [query, setQuery] = useState('');
  const [search, setSearch] = useState('');
  const [bookings, setBookings] = useState(null);
  const [error, setError] = useState(null);
  const [reloads, setReloads] = useState(0);

  useEffect(() => {
    const timer = setTimeout(() => setSearch(query.trim()), SEARCH_DELAY_MS);
    return () => clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    let cancelled = false;
    salesService
      .bookings({ q: search, limit: LIMIT })
      .then((found) => {
        if (cancelled) return;
        setBookings(found);
        setError(null);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      });
    return () => {
      cancelled = true;
    };
  }, [search, reloads]);

  return (
    <>
      <h1>Bookings</h1>
      <p className="admin__lead">
        What guests have bought, newest first. Every booking sends the guest a
        confirmation with its reference, which they show at the entrance.
      </p>

      <div className="admin-toolbar">
        <label className="admin-search">
          <span className="visually-hidden">Search bookings</span>
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Booking reference or e-mail address"
            maxLength={254}
          />
        </label>
        <button type="button" onClick={() => setReloads((n) => n + 1)}>
          Refresh
        </button>
      </div>

      {error && (
        <p className="admin-login__error" role="alert">
          {error}
        </p>
      )}

      {bookings === null ? (
        !error && <p className="admin-status">Loading bookings…</p>
      ) : bookings.length === 0 ? (
        <p className="admin-empty">
          {search
            ? `No booking matches "${search}".`
            : 'No bookings yet. They appear here as soon as a guest books.'}
        </p>
      ) : (
        <>
          <AdminBookingList bookings={bookings} programme={programme} />
          {bookings.length === LIMIT && (
            <p className="admin-manage__note">
              The latest {LIMIT} bookings. Search for an older one by its
              reference or e-mail address.
            </p>
          )}
        </>
      )}
    </>
  );
}

export default AdminBookingsPage;
