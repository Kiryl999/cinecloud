import { useRef, useState } from 'react';

/** State of a list with a form beside it, as on the movie, hall and showtime
    pages: the form adds an item, or changes the one picked from the list.

    `empty` is what the form holds while adding - pass a constant, not a new
    object on every render. `refresh` reloads the list after every change. */
export function useEditor(empty, refresh) {
  const [values, setValues] = useState(empty);
  // the item picked from the list, null while adding a new one
  const [editing, setEditing] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  // says what the last save did, until the form is touched again
  const [notice, setNotice] = useState(null);
  // a failed delete, shown above the list rather than in the form
  const [listError, setListError] = useState(null);
  const formRef = useRef(null);

  /** Props for an input bound to `name`: <input {...editor.field('title')} /> */
  function field(name) {
    return {
      value: values[name],
      onChange: (event) => {
        setValues((current) => ({ ...current, [name]: event.target.value }));
        setNotice(null);
      },
    };
  }

  /** Loads `item` into the form, as `itemValues`. */
  function edit(item, itemValues) {
    setEditing(item);
    setValues(itemValues);
    setError(null);
    setNotice(null);
    // on a phone the form sits above the list, out of sight
    formRef.current?.querySelector('input:not(:disabled), select:not(:disabled)')?.focus();
  }

  function cancel() {
    setEditing(null);
    setValues(empty);
    setError(null);
  }

  /** Submit handler for the form. `save(values, editing)` sends the request
      and returns the notice to show; whatever it throws ends up as the
      form's error. With `keep`, an added item's values stay in the form, so
      the next one only needs what differs. */
  function submit(save, { keep = false } = {}) {
    return async (event) => {
      event.preventDefault();
      setSaving(true);
      setError(null);
      setNotice(null);
      setListError(null);

      let message;
      try {
        message = await save(values, editing);
      } catch (err) {
        setError(err.message);
        setSaving(false);
        return;
      }

      // the item is saved even if the reload fails, so the form moves on
      try {
        await refresh();
      } catch (err) {
        setListError(err.message);
      }
      if (editing || !keep) setValues(empty);
      setEditing(null);
      setNotice(message);
      setSaving(false);
    };
  }

  /** Deletes through `del(item)` once the admin confirms `question`. */
  async function remove(item, question, del) {
    if (!window.confirm(question)) return;
    setListError(null);
    setNotice(null);
    try {
      await del(item);
      if (editing?.id === item.id) cancel();
      await refresh();
    } catch (err) {
      setListError(err.message);
    }
  }

  return {
    values,
    editing,
    saving,
    error,
    notice,
    listError,
    formRef,
    field,
    edit,
    cancel,
    submit,
    remove,
  };
}
