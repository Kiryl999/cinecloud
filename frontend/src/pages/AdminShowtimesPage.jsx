import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import AdminEditor from '../components/AdminEditor';
import { useEditor } from '../hooks/useEditor';
import { useNow } from '../hooks/useNow';
import { useProgramme } from '../hooks/useProgramme';
import { showtimeService } from '../services/api';
import {
  dayKey,
  formatDay,
  formatPrice,
  formatTime,
  fromDateTimeInput,
  toDateTimeInput,
} from '../utils/format';

const EMPTY = { movie_id: '', hall_id: '', start: '', ticket_price: '' };

// the backend's rule, see backend/app/api/scheduling.py: a hall needs this
// long after each showtime for cleaning and admission
const TURNAROUND_MINUTES = 15;

const MINUTE = 60_000;

const endOf = (showtime, movieById) =>
  new Date(showtime.start_time).getTime() +
  movieById.get(showtime.movie_id).duration_minutes * MINUTE;

/** The showtime that `planned` would run into in the same hall, if any.

    The backend checks this as well, and only its check counts: it sees
    changes other admins make meanwhile. This one runs first so the admin
    reads which showtime is in the way, at the cinema's time rather than in
    UTC. */
function findClash(planned, ignoreId, { showtimes, movieById }) {
  const start = new Date(planned.start_time).getTime();
  const end = endOf(planned, movieById) + TURNAROUND_MINUTES * MINUTE;
  return showtimes.find(
    (other) =>
      other.id !== ignoreId &&
      other.hall_id === planned.hall_id &&
      new Date(other.start_time).getTime() < end &&
      endOf(other, movieById) + TURNAROUND_MINUTES * MINUTE > start,
  );
}

function AdminShowtimesPage() {
  const { programme, refresh } = useProgramme();
  const { movies, halls, movieById, hallById } = programme;
  const editor = useEditor(EMPTY, refresh);
  const now = useNow(60_000);
  const [showPast, setShowPast] = useState(false);

  // grouped by the day they start, a showtime counting as past once it ended
  const { days, pastCount } = useMemo(() => {
    const groups = new Map();
    let past = 0;
    for (const showtime of programme.showtimes) {
      if (endOf(showtime, movieById) < now) {
        past += 1;
        if (!showPast) continue;
      }
      const key = dayKey(showtime.start_time);
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(showtime);
    }
    return { days: [...groups.values()], pastCount: past };
  }, [programme.showtimes, movieById, now, showPast]);

  async function save(values, editing) {
    const planned = {
      movie_id: Number(values.movie_id),
      // a showtime stays in its hall
      hall_id: editing ? editing.hall_id : Number(values.hall_id),
      start_time: fromDateTimeInput(values.start),
      ticket_price: values.ticket_price,
    };
    const movie = movieById.get(planned.movie_id);
    const hall = hallById.get(planned.hall_id);

    const clash = findClash(planned, editing?.id, programme);
    if (clash) {
      throw new Error(
        `${hall.name} is in use then: ${movieById.get(clash.movie_id).title} ` +
          `plays from ${formatTime(clash.start_time)} to ` +
          `${formatTime(endOf(clash, movieById))} on ${formatDay(clash.start_time)}, ` +
          `and the hall needs ${TURNAROUND_MINUTES} minutes after each showtime.`,
      );
    }

    const when = `${formatDay(planned.start_time)}, ${formatTime(planned.start_time)}`;
    if (editing) {
      const { movie_id, start_time, ticket_price } = planned;
      await showtimeService.update(editing.id, { movie_id, start_time, ticket_price });
      return `Saved: ${movie.title}, ${when}.`;
    }
    await showtimeService.create(planned);
    return `Added: ${movie.title}, ${when} in ${hall.name}. Change the time to add another.`;
  }

  if (movies.length === 0 || halls.length === 0) {
    return (
      <>
        <h1>Showtimes</h1>
        <p className="admin-empty">
          A showtime is a movie in a hall at a time.{' '}
          {halls.length === 0 ? (
            <Link to="/admin/halls">Add a hall first</Link>
          ) : (
            <Link to="/admin/movies">Add a movie first</Link>
          )}
        </p>
      </>
    );
  }

  return (
    <>
      <h1>Showtimes</h1>
      <p className="admin__lead">
        Your programme, in the local time of the cinema. Upcoming showtimes
        appear on your visitor page, where they can be booked.
      </p>

      <div className="admin-manage">
        <AdminEditor
          editor={editor}
          title={editor.editing ? 'Edit showtime' : 'Plan a showtime'}
          addLabel="Add showtime"
          onSave={save}
          keep
        >
          <label htmlFor="showtime-movie">Movie</label>
          <select id="showtime-movie" {...editor.field('movie_id')} required>
            <option value="" disabled>
              Choose a movie
            </option>
            {movies.map((movie) => (
              <option key={movie.id} value={movie.id}>
                {movie.title}
              </option>
            ))}
          </select>

          <label htmlFor="showtime-hall">Hall</label>
          <select
            id="showtime-hall"
            {...editor.field('hall_id')}
            disabled={Boolean(editor.editing)}
            required
          >
            <option value="" disabled>
              Choose a hall
            </option>
            {halls.map((hall) => (
              <option key={hall.id} value={hall.id}>
                {hall.name} ({hall.seat_count} seats)
              </option>
            ))}
          </select>
          {editor.editing && (
            <p className="admin-editor__hint">
              A showtime stays in its hall: its tickets are for seats there.
              To move it, delete it and plan a new one.
            </p>
          )}

          <div className="admin-editor__pair">
            <div>
              <label htmlFor="showtime-start">Starts</label>
              <input
                id="showtime-start"
                type="datetime-local"
                {...editor.field('start')}
                required
              />
            </div>
            <div>
              <label htmlFor="showtime-price">Ticket (€)</label>
              <input
                id="showtime-price"
                type="number"
                {...editor.field('ticket_price')}
                min={0}
                max={999.99}
                step={0.01}
                placeholder="9.50"
                required
              />
            </div>
          </div>
        </AdminEditor>

        <section className="admin-manage__list" aria-label="Your showtimes">
          {editor.listError && (
            <p className="admin-login__error" role="alert">
              {editor.listError}
            </p>
          )}

          {pastCount > 0 && (
            <label className="admin-toggle">
              <input
                type="checkbox"
                checked={showPast}
                onChange={(event) => setShowPast(event.target.checked)}
              />
              Show {pastCount === 1 ? 'the past showtime' : `${pastCount} past showtimes`}
            </label>
          )}

          {days.length === 0 ? (
            <p className="admin-empty">No upcoming showtimes.</p>
          ) : (
            days.map((showtimes) => (
              <div key={dayKey(showtimes[0].start_time)} className="admin-day">
                <h2 className="admin__heading">{formatDay(showtimes[0].start_time)}</h2>
                <ul className="admin-list">
                  {showtimes.map((showtime) => {
                    const movie = movieById.get(showtime.movie_id);
                    const hall = hallById.get(showtime.hall_id);
                    const past = endOf(showtime, movieById) < now;
                    return (
                      <li
                        key={showtime.id}
                        className={
                          'admin-row' +
                          (past ? ' admin-row--past' : '') +
                          (editor.editing?.id === showtime.id ? ' admin-row--editing' : '')
                        }
                      >
                        <div className="admin-row__main">
                          <strong>
                            {formatTime(showtime.start_time)} {movie.title}
                          </strong>
                          <span className="admin-row__meta">
                            until {formatTime(endOf(showtime, movieById))} · {hall.name} ·{' '}
                            {formatPrice(showtime.ticket_price)}
                          </span>
                        </div>
                        <div className="admin-row__actions">
                          <button
                            type="button"
                            onClick={() =>
                              editor.edit(showtime, {
                                movie_id: String(showtime.movie_id),
                                hall_id: String(showtime.hall_id),
                                start: toDateTimeInput(showtime.start_time),
                                ticket_price: showtime.ticket_price,
                              })
                            }
                          >
                            Edit
                          </button>
                          <button
                            type="button"
                            className="admin-row__delete"
                            onClick={() =>
                              editor.remove(
                                showtime,
                                `Delete ${movie.title} on ${formatDay(showtime.start_time)} at ${formatTime(showtime.start_time)}?`,
                                () => showtimeService.remove(showtime.id),
                              )
                            }
                          >
                            Delete
                          </button>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))
          )}
          <p className="admin-manage__note">
            A showtime that has sold tickets cannot be deleted.
          </p>
        </section>
      </div>
    </>
  );
}

export default AdminShowtimesPage;
