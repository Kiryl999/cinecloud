import { useMemo } from 'react';

import AdminEditor from '../components/AdminEditor';
import { useEditor } from '../hooks/useEditor';
import { useProgramme } from '../hooks/useProgramme';
import { movieService } from '../services/api';
import { formatDuration } from '../utils/format';

const EMPTY = { title: '', release_year: '', duration_minutes: '', description: '' };

function AdminMoviesPage() {
  const { programme, refresh } = useProgramme();
  const editor = useEditor(EMPTY, refresh);

  const showtimeCount = useMemo(() => {
    const counts = new Map();
    for (const showtime of programme.showtimes) {
      counts.set(showtime.movie_id, (counts.get(showtime.movie_id) ?? 0) + 1);
    }
    return counts;
  }, [programme.showtimes]);

  async function save(values, editing) {
    const movie = {
      title: values.title.trim(),
      release_year: Number(values.release_year),
      duration_minutes: Number(values.duration_minutes),
      description: values.description.trim(),
    };
    if (editing) {
      await movieService.update(editing.id, movie);
      return `Saved ${movie.title}.`;
    }
    await movieService.create(movie);
    return `Added ${movie.title}. It can be scheduled now.`;
  }

  return (
    <>
      <h1>Movies</h1>
      <p className="admin__lead">
        The films your cinema shows. A movie can be scheduled as often as you
        like, under Showtimes.
      </p>

      <div className="admin-manage">
        <AdminEditor
          editor={editor}
          title={editor.editing ? `Edit ${editor.editing.title}` : 'Add a movie'}
          addLabel="Add movie"
          onSave={save}
        >
          <label htmlFor="movie-title">Title</label>
          <input id="movie-title" {...editor.field('title')} maxLength={200} required />

          <div className="admin-editor__pair">
            <div>
              <label htmlFor="movie-year">Year</label>
              <input
                id="movie-year"
                type="number"
                {...editor.field('release_year')}
                min={1888}
                max={2200}
                placeholder="2024"
                required
              />
            </div>
            <div>
              <label htmlFor="movie-duration">Minutes</label>
              <input
                id="movie-duration"
                type="number"
                {...editor.field('duration_minutes')}
                min={1}
                max={1000}
                placeholder="120"
                required
              />
            </div>
          </div>
          {editor.editing && (
            <p className="admin-editor__hint">
              A new length moves the end of every showtime of this movie. If one
              would run into the next showtime in its hall, the change is
              refused.
            </p>
          )}

          <label htmlFor="movie-description">Description</label>
          <textarea
            id="movie-description"
            {...editor.field('description')}
            rows={4}
            maxLength={2000}
          />
        </AdminEditor>

        <section className="admin-manage__list" aria-label="Your movies">
          {editor.listError && (
            <p className="admin-login__error" role="alert">
              {editor.listError}
            </p>
          )}

          {programme.movies.length === 0 ? (
            <p className="admin-empty">No movies yet.</p>
          ) : (
            <ul className="admin-list">
              {programme.movies.map((movie) => {
                const count = showtimeCount.get(movie.id) ?? 0;
                return (
                  <li
                    key={movie.id}
                    className={`admin-row${editor.editing?.id === movie.id ? ' admin-row--editing' : ''}`}
                  >
                    <div className="admin-row__main">
                      <strong>{movie.title}</strong>
                      <span className="admin-row__meta">
                        {movie.release_year} · {formatDuration(movie.duration_minutes)} ·{' '}
                        {count === 1 ? '1 showtime' : `${count} showtimes`}
                      </span>
                    </div>
                    <div className="admin-row__actions">
                      <button
                        type="button"
                        onClick={() =>
                          editor.edit(movie, {
                            title: movie.title,
                            release_year: String(movie.release_year),
                            duration_minutes: String(movie.duration_minutes),
                            description: movie.description,
                          })
                        }
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        className="admin-row__delete"
                        onClick={() =>
                          editor.remove(movie, `Delete ${movie.title}?`, () =>
                            movieService.remove(movie.id),
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
          )}
          {programme.movies.length > 0 && (
            <p className="admin-manage__note">
              A movie with showtimes cannot be deleted - delete its showtimes
              first. Once one has sold tickets, the movie stays.
            </p>
          )}
        </section>
      </div>
    </>
  );
}

export default AdminMoviesPage;
