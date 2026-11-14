/** The form beside a list in the operator area. It adds an item, or changes
    the one picked from the list; `editor` comes from useEditor. */
function AdminEditor({ editor, title, addLabel, onSave, keep = false, children }) {
  return (
    <form
      ref={editor.formRef}
      className="admin-editor"
      onSubmit={editor.submit(onSave, { keep })}
    >
      <h2>{title}</h2>

      {children}

      {editor.error && (
        <p className="admin-login__error" role="alert">
          {editor.error}
        </p>
      )}
      <p className="admin-editor__notice" role="status">
        {editor.notice}
      </p>

      <div className="admin-editor__buttons">
        <button type="submit" className="cta" disabled={editor.saving}>
          {editor.saving ? 'Saving…' : editor.editing ? 'Save changes' : addLabel}
        </button>
        {editor.editing && (
          <button type="button" className="admin-editor__cancel" onClick={editor.cancel}>
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}

export default AdminEditor;
