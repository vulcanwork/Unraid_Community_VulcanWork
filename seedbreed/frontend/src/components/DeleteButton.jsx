import { useState } from 'react';
import { api } from '../api.js';

// Delete button with a confirm step. If the backend refuses because other
// records depend on this one (409 delete_blocked), shows what is in the way
// and offers to delete it all with ?cascade=true.
export default function DeleteButton({ path, label, confirmText, onDeleted }) {
  const [blocked, setBlocked] = useState(null);
  const [busy, setBusy] = useState(false);

  const onClick = async () => {
    if (busy) return;
    if (!confirm(confirmText || `Delete "${label}"?`)) return;
    setBusy(true);
    try {
      await api.del(path);
      // Stay disabled on success: the row goes away once onDeleted reloads.
      onDeleted();
    } catch (e) {
      setBusy(false);
      if (e.detail && e.detail.error === 'delete_blocked') setBlocked(e.detail);
      else alert(e.message);
    }
  };

  const deleteAll = async () => {
    if (busy) return;
    setBusy(true);
    try {
      await api.del(`${path}?cascade=true`);
      setBlocked(null);
      // Stay disabled on success: the row goes away once onDeleted reloads.
      onDeleted();
    } catch (e) {
      setBusy(false);
      alert(e.message);
    }
  };

  return (
    <>
      <button className="small-btn danger" disabled={busy} onClick={onClick}>Delete</button>
      {blocked && (
        <div className="modal-backdrop" onClick={() => !busy && setBlocked(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Can’t delete "{label}"</h2>
            <p>{blocked.message}</p>
            {(blocked.blocked_by || []).map((b, i) => (
              <div key={`${i}-${b.label}`} className="list-row">
                <div className="list-row-main">{b.label}</div>
                <span className="muted small">
                  {b.action === 'delete' ? 'will be deleted' : 'will be unlinked'}
                </span>
              </div>
            ))}
            <div className="modal-actions">
              <button disabled={busy} onClick={() => setBlocked(null)}>Cancel</button>
              <button className="primary" disabled={busy} onClick={deleteAll}>
                {busy ? 'Deleting…' : 'Delete all'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
