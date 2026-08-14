import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api.js';

export default function Seeds() {
  const [seeds, setSeeds] = useState([]);
  const [strains, setStrains] = useState([]);
  const [showNew, setShowNew] = useState(false);
  const [editSeed, setEditSeed] = useState(null);

  const load = async () => {
    const [s, st] = await Promise.all([api.get('/api/seeds'), api.get('/api/strains')]);
    setSeeds(s); setStrains(st);
  };
  useEffect(() => { load(); }, []);

  return (
    <>
      <div className="page-header flex-between">
        <div>
          <div className="eyebrow">Inventory</div>
          <h1>Seeds</h1>
        </div>
        <button className="primary" onClick={() => setShowNew(true)}>+ Add seeds</button>
      </div>

      {seeds.length === 0 ? (
        <div className="empty card">
          <div className="empty-title">No seeds tracked yet</div>
          <div className="small muted">Log purchased, gifted, or self-produced seeds here.</div>
        </div>
      ) : (
        <div className="list">
          {seeds.map((s) => (
            <div key={s.id} className="list-row">
              <div className="list-row-main">
                <div className="list-row-title">
                  {s.strain_name || `Strain #${s.strain_id}`}
                  <span className={`badge ${s.origin}`} style={{ marginLeft: 10 }}>{s.origin}</span>
                  {s.feminized && <span className="badge" style={{ marginLeft: 6 }}>feminized</span>}
                  {s.auto_flower && <span className="badge" style={{ marginLeft: 6 }}>auto</span>}
                </div>
                <div className="list-row-meta">
                  {seedCountLabel(s)}
                  {s.acquired_date ? ` · acquired ${s.acquired_date}` : ''}
                  {s.source_label ? ` · ${s.source_label}` : ''}
                </div>
                {s.notes && <div className="small mt-2">{s.notes}</div>}
              </div>
              <div className="row-actions">
                <button className="small-btn" onClick={() => setEditSeed(s)}>Edit</button>
                <Link to={`/strains/${s.strain_id}`} className="muted small">view strain →</Link>
              </div>
            </div>
          ))}
        </div>
      )}

      {(showNew || editSeed) && (
        <SeedModal
          strains={strains}
          existing={editSeed}
          onClose={() => { setShowNew(false); setEditSeed(null); }}
          onSaved={() => { setShowNew(false); setEditSeed(null); load(); }}
        />
      )}
    </>
  );
}

function seedCountLabel(s) {
  if (s.quantity != null) {
    const remaining = s.seeds_remaining ?? s.quantity;
    return `${remaining} of ${s.quantity} seeds remaining`;
  }
  if (s.seeds_remaining != null) return `${s.seeds_remaining} seeds remaining`;
  return 'batch';
}

function SeedModal({ strains, existing, onClose, onSaved }) {
  const isEdit = !!existing;
  const [form, setForm] = useState(() => existing ? {
    strain_id: String(existing.strain_id),
    origin: existing.origin || 'purchased',
    source_label: existing.source_label || '',
    acquired_date: existing.acquired_date || '',
    quantity: existing.quantity ?? '',
    seeds_remaining: existing.seeds_remaining ?? '',
    feminized: !!existing.feminized,
    auto_flower: !!existing.auto_flower,
    notes: existing.notes || '',
  } : {
    strain_id: '', origin: 'purchased', source_label: '', acquired_date: '',
    quantity: '', seeds_remaining: '', feminized: false, auto_flower: false, notes: '',
  });
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    try {
      const payload = {
        ...form,
        strain_id: parseInt(form.strain_id),
        quantity: form.quantity !== '' ? parseInt(form.quantity) : null,
        seeds_remaining: form.seeds_remaining !== '' ? parseInt(form.seeds_remaining) : null,
        acquired_date: form.acquired_date || null,
      };
      if (isEdit) {
        await api.patch(`/api/seeds/${existing.id}`, payload);
      } else {
        await api.post('/api/seeds', payload);
      }
      onSaved();
    } catch (e) { alert(e.message); setBusy(false); }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>{isEdit ? 'Edit seeds' : 'Add seeds'}</h2>
        <div className="field">
          <label>Strain</label>
          <select value={form.strain_id} onChange={(e) => setForm({ ...form, strain_id: e.target.value })}>
            <option value="">— Select strain —</option>
            {strains.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </div>
        <div className="grid grid-2">
          <div className="field">
            <label>Origin</label>
            <select value={form.origin} onChange={(e) => setForm({ ...form, origin: e.target.value })}>
              <option value="purchased">Purchased</option>
              <option value="gifted">Gifted</option>
              <option value="produced">Self-produced</option>
              <option value="unknown">Unknown</option>
            </select>
          </div>
          <div className="field">
            <label>Quantity</label>
            <input type="number" value={form.quantity}
                   onChange={(e) => setForm({ ...form, quantity: e.target.value })} />
          </div>
        </div>
        <div className="grid grid-2">
          <div className="field">
            <label>Seeds remaining</label>
            <input type="number" value={form.seeds_remaining}
                   onChange={(e) => setForm({ ...form, seeds_remaining: e.target.value })}
                   placeholder={isEdit ? '' : 'Defaults to quantity'} />
          </div>
          <div className="field">
            <label>Acquired date</label>
            <input type="date" value={form.acquired_date}
                   onChange={(e) => setForm({ ...form, acquired_date: e.target.value })} />
          </div>
        </div>
        <div className="grid grid-2">
          <label className="checkbox-field">
            <input type="checkbox" checked={form.feminized}
                   onChange={(e) => setForm({ ...form, feminized: e.target.checked })} />
            Feminized
          </label>
          <label className="checkbox-field">
            <input type="checkbox" checked={form.auto_flower}
                   onChange={(e) => setForm({ ...form, auto_flower: e.target.checked })} />
            Auto flower
          </label>
        </div>
        <div className="field">
          <label>Source</label>
          <input value={form.source_label}
                 onChange={(e) => setForm({ ...form, source_label: e.target.value })}
                 placeholder="Seed bank, friend's name, etc." />
        </div>
        <div className="field">
          <label>Notes</label>
          <textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
        </div>
        <div className="modal-actions">
          <button onClick={onClose}>Cancel</button>
          <button className="primary" disabled={busy || !form.strain_id} onClick={submit}>
            {busy ? 'Saving…' : isEdit ? 'Save changes' : 'Add seeds'}
          </button>
        </div>
      </div>
    </div>
  );
}
