import { useMemo } from 'react';

import AdminEditor from '../components/AdminEditor';
import { useEditor } from '../hooks/useEditor';
import { useProgramme } from '../hooks/useProgramme';
import { hallService } from '../services/api';

const EMPTY = { name: '', rows: '', seats_per_row: '' };

function AdminHallsPage() {
  const { programme, refresh } = useProgramme();
  const editor = useEditor(EMPTY, refresh);

  const showtimeCount = useMemo(() => {
    const counts = new Map();
    for (const showtime of programme.showtimes) {
      counts.set(showtime.hall_id, (counts.get(showtime.hall_id) ?? 0) + 1);
    }
    return counts;
  }, [programme.showtimes]);

  async function save(values, editing) {
    const name = values.name.trim();
    // the seat plan is fixed once the hall exists, only the name changes
    if (editing) {
      await hallService.update(editing.id, { name });
      return `Saved ${name}.`;
    }
    const hall = await hallService.create({
      name,
      rows: Number(values.rows),
      seats_per_row: Number(values.seats_per_row),
    });
    return `Added ${hall.name} with ${hall.seat_count} seats.`;
  }

  const seatCount = Number(editor.values.rows) * Number(editor.values.seats_per_row);

  return (
    <>
      <h1>Halls</h1>
      <p className="admin__lead">
        Where your showtimes play. Each hall has a grid of seats, which visitors
        pick from when they book.
      </p>

      <div className="admin-manage">
        <AdminEditor
          editor={editor}
          title={editor.editing ? `Edit ${editor.editing.name}` : 'Add a hall'}
          addLabel="Add hall"
          onSave={save}
        >
          <label htmlFor="hall-name">Name</label>
          <input
            id="hall-name"
            {...editor.field('name')}
            maxLength={100}
            placeholder="Saal 1"
            required
          />

          {editor.editing ? (
            <p className="admin-editor__hint">
              {editor.editing.seat_count} seats. The seat plan stays as it is: sold
              and reserved tickets point at its seats.
            </p>
          ) : (
            <>
              <div className="admin-editor__pair">
                <div>
                  <label htmlFor="hall-rows">Rows</label>
                  <input
                    id="hall-rows"
                    type="number"
                    {...editor.field('rows')}
                    min={1}
                    max={100}
                    placeholder="8"
                    required
                  />
                </div>
                <div>
                  <label htmlFor="hall-seats">Seats per row</label>
                  <input
                    id="hall-seats"
                    type="number"
                    {...editor.field('seats_per_row')}
                    min={1}
                    max={100}
                    placeholder="12"
                    required
                  />
                </div>
              </div>
              <p className="admin-editor__hint">
                {seatCount > 0
                  ? `${seatCount} seats. They cannot be changed later.`
                  : 'The seat plan cannot be changed later.'}
              </p>
            </>
          )}
        </AdminEditor>

        <section className="admin-manage__list" aria-label="Your halls">
          {editor.listError && (
            <p className="admin-login__error" role="alert">
              {editor.listError}
            </p>
          )}

          {programme.halls.length === 0 ? (
            <p className="admin-empty">No halls yet.</p>
          ) : (
            <ul className="admin-list">
              {programme.halls.map((hall) => {
                const count = showtimeCount.get(hall.id) ?? 0;
                return (
                  <li
                    key={hall.id}
                    className={`admin-row${editor.editing?.id === hall.id ? ' admin-row--editing' : ''}`}
                  >
                    <div className="admin-row__main">
                      <strong>{hall.name}</strong>
                      <span className="admin-row__meta">
                        {hall.seat_count} seats ·{' '}
                        {count === 1 ? '1 showtime' : `${count} showtimes`}
                      </span>
                    </div>
                    <div className="admin-row__actions">
                      <button
                        type="button"
                        onClick={() => editor.edit(hall, { ...EMPTY, name: hall.name })}
                      >
                        Rename
                      </button>
                      <button
                        type="button"
                        className="admin-row__delete"
                        onClick={() =>
                          editor.remove(hall, `Delete ${hall.name}?`, () =>
                            hallService.remove(hall.id),
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
          {programme.halls.length > 0 && (
            <p className="admin-manage__note">
              A hall with showtimes cannot be deleted - delete its showtimes
              first.
            </p>
          )}
        </section>
      </div>
    </>
  );
}

export default AdminHallsPage;
