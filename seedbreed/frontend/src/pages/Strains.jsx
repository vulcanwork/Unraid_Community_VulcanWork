import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api.js';

export default function Strains() {
  const [strains, setStrains] = useState([]);
  const [showNew, setShowNew] = useState(false);
  const [editStrain, setEditStrain] = useState(null);

  const load = () => api.get('/api/strains').then(setStrains);
  useEffect(() => { load(); }, []);

  return (
    <>
      <div className="page-header flex-between">
        <div>
          <div className="eyebrow">Library</div>
          <h1>Strains</h1>
        </div>
        <button className="primary" onClick={() => setShowNew(true)}>+ New strain</button>
      </div>

      {strains.length === 0 ? (
        <div className="empty card">
          <div className="empty-title">No strains in your library</div>
          <div className="small muted">Add your first strain to start tracking genetics.</div>
        </div>
      ) : (
        <div className="list">
          {strains.map((s) => (
            <div key={s.id} className="list-row">
              <div className="list-row-main">
                <div className="list-row-title">{s.name}</div>
                <div className="list-row-meta">
                  {s.type || 'unknown type'}
                  {s.breeder ? ` · ${s.breeder}` : ''}
                  {s.indica_pct != null ? ` · ${s.indica_pct}% indica` : ''}
                  {s.sativa_pct != null ? ` · ${s.sativa_pct}% sativa` : ''}
                  {s.thc_pct != null ? ` · ${s.thc_pct}% THC` : ''}
                  {(s.parent_a_id || s.parent_b_id) ? ' · has parents' : ''}
                </div>
              </div>
              <div className="row-actions">
                <button className="small-btn" onClick={() => setEditStrain(s)}>Edit</button>
                <Link to={`/strains/${s.id}`} className="muted small">view →</Link>
              </div>
            </div>
          ))}
        </div>
      )}

      {(showNew || editStrain) && (
        <StrainModal
          existing={editStrain}
          allStrains={strains}
          onClose={() => { setShowNew(false); setEditStrain(null); }}
          onSaved={() => { setShowNew(false); setEditStrain(null); load(); }}
        />
      )}
    </>
  );
}

function StrainModal({ existing, allStrains, onClose, onSaved }) {
  const isEdit = !!existing;
  const [form, setForm] = useState(() => existing ? {
    name: existing.name || '',
    breeder: existing.breeder || '',
    type: existing.type || 'hybrid',
    indica_pct: existing.indica_pct ?? '',
    sativa_pct: existing.sativa_pct ?? '',
    thc_pct: existing.thc_pct ?? '',
    parent_a_id: existing.parent_a_id ? String(existing.parent_a_id) : '',
    parent_b_id: existing.parent_b_id ? String(existing.parent_b_id) : '',
    notes: existing.notes || '',
  } : {
    name: '', breeder: '', type: 'hybrid', indica_pct: '', sativa_pct: '', thc_pct: '',
    parent_a_id: '', parent_b_id: '', notes: '',
  });
  const [busy, setBusy] = useState(false);

  // A strain can't be its own parent, so leave it out of the parent pickers when editing.
  const parentOptions = allStrains.filter((s) => !isEdit || s.id !== existing.id);

  const submit = async () => {
    setBusy(true);
    try {
      const payload = {
        ...form,
        indica_pct: form.indica_pct !== '' ? parseFloat(form.indica_pct) : null,
        sativa_pct: form.sativa_pct !== '' ? parseFloat(form.sativa_pct) : null,
        thc_pct: form.thc_pct !== '' ? parseFloat(form.thc_pct) : null,
        parent_a_id: form.parent_a_id ? parseInt(form.parent_a_id) : null,
        parent_b_id: form.parent_b_id ? parseInt(form.parent_b_id) : null,
      };
      if (isEdit) {
        await api.patch(`/api/strains/${existing.id}`, payload);
      } else {
        await api.post('/api/strains', payload);
      }
      onSaved();
    } catch (e) { alert(e.message); setBusy(false); }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>{isEdit ? 'Edit strain' : 'New strain'}</h2>
        <div className="field">
          <label>Name</label>
          <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </div>
        <div className="grid grid-2">
          <div className="field">
            <label>Breeder / source</label>
            <input value={form.breeder} onChange={(e) => setForm({ ...form, breeder: e.target.value })} />
          </div>
          <div className="field">
            <label>Type</label>
            <select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>
              <option value="indica">Indica</option>
              <option value="sativa">Sativa</option>
              <option value="hybrid">Hybrid</option>
              <option value="ruderalis">Ruderalis / Auto</option>
            </select>
          </div>
        </div>
        <div className="grid grid-3">
          <div className="field">
            <label>Indica %</label>
            <input type="number" min="0" max="100" step="0.1" value={form.indica_pct}
                   onChange={(e) => setForm({ ...form, indica_pct: e.target.value })} />
          </div>
          <div className="field">
            <label>Sativa %</label>
            <input type="number" min="0" max="100" step="0.1" value={form.sativa_pct}
                   onChange={(e) => setForm({ ...form, sativa_pct: e.target.value })} />
          </div>
          <div className="field">
            <label>THC %</label>
            <input type="number" min="0" max="100" step="0.1" value={form.thc_pct}
                   onChange={(e) => setForm({ ...form, thc_pct: e.target.value })} />
          </div>
        </div>
        <div className="grid grid-2">
          <div className="field">
            <label>Parent A (optional)</label>
            <select value={form.parent_a_id} onChange={(e) => setForm({ ...form, parent_a_id: e.target.value })}>
              <option value="">— None —</option>
              {parentOptions.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
          <div className="field">
            <label>Parent B (optional)</label>
            <select value={form.parent_b_id} onChange={(e) => setForm({ ...form, parent_b_id: e.target.value })}>
              <option value="">— None —</option>
              {parentOptions.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
        </div>
        <div className="field">
          <label>Notes</label>
          <textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
        </div>
        <div className="modal-actions">
          <button onClick={onClose}>Cancel</button>
          <button className="primary" disabled={busy || !form.name.trim()} onClick={submit}>
            {busy ? 'Saving…' : isEdit ? 'Save changes' : 'Save strain'}
          </button>
        </div>
      </div>
    </div>
  );
}
