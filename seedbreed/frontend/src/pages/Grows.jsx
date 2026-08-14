import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api.js';

export default function Grows() {
  const [grows, setGrows] = useState([]);
  const [showNew, setShowNew] = useState(false);

  const load = () => api.get('/api/grows').then(setGrows);
  useEffect(() => { load(); }, []);

  return (
    <>
      <div className="page-header flex-between">
        <div>
          <div className="eyebrow">All cycles</div>
          <h1>Grows</h1>
        </div>
        <button className="primary" onClick={() => setShowNew(true)}>+ New grow</button>
      </div>

      {grows.length === 0 ? (
        <div className="empty card">
          <div className="empty-title">No grows yet</div>
          <div className="small muted">Click "New grow" to start tracking your first cycle.</div>
        </div>
      ) : (
        <div className="list">
          {grows.map((g) => (
            <Link key={g.id} to={`/grows/${g.id}`} className="list-row">
              <div className="list-row-main">
                <div className="list-row-title">{g.name}</div>
                <div className="list-row-meta">
                  {g.start_date || '—'}
                  {g.end_date ? ` → ${g.end_date}` : ''}
                  {' · '}{g.location || 'no location'}
                  {' · '}{g.groups?.length || 0} group{g.groups?.length === 1 ? '' : 's'}
                </div>
              </div>
              <div className="muted small">→</div>
            </Link>
          ))}
        </div>
      )}

      {showNew && <NewGrowModal onClose={() => setShowNew(false)} onCreated={() => { setShowNew(false); load(); }} />}
    </>
  );
}

function defaultGroup(i) {
  return {
    name: `Group ${i + 1}`,
    fertilizer_type: i === 1 ? 'chemical' : 'natural',
    description: '',
    identifier: '',
  };
}

function NewGrowModal({ onClose, onCreated }) {
  const [form, setForm] = useState({
    name: '', start_date: '', location: '', notes: '',
    groups: [defaultGroup(0), defaultGroup(1)],
  });
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    try {
      await api.post('/api/grows', {
        ...form,
        start_date: form.start_date || null,
        groups: form.groups.filter((g) => g.name.trim()),
      });
      onCreated();
    } catch (e) {
      alert(e.message);
      setBusy(false);
    }
  };

  const setGroupCount = (n) => {
    const groups = form.groups.slice(0, n);
    while (groups.length < n) groups.push(defaultGroup(groups.length));
    setForm({ ...form, groups });
  };

  const updateGroup = (i, patch) => {
    const groups = [...form.groups];
    groups[i] = { ...groups[i], ...patch };
    setForm({ ...form, groups });
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>New grow</h2>

        <div className="field">
          <label>Name</label>
          <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                 placeholder="e.g. 2026 Cannabis Grow Test" />
        </div>
        <div className="grid grid-2">
          <div className="field">
            <label>Start date</label>
            <input type="date" value={form.start_date}
                   onChange={(e) => setForm({ ...form, start_date: e.target.value })} />
          </div>
          <div className="field">
            <label>Location</label>
            <input value={form.location}
                   onChange={(e) => setForm({ ...form, location: e.target.value })}
                   placeholder="Greenhouse tent" />
          </div>
        </div>
        <div className="field">
          <label>Notes</label>
          <textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
        </div>

        <h3 className="mt-4">Groups</h3>
        <p className="small muted">Two or more groups make side-by-side comparison possible.</p>
        <div className="field">
          <label>Number of groups</label>
          <select value={form.groups.length}
                  onChange={(e) => setGroupCount(parseInt(e.target.value))}>
            <option value={1}>1</option>
            <option value={2}>2</option>
            <option value={3}>3</option>
            <option value={4}>4</option>
          </select>
        </div>
        {form.groups.map((g, i) => (
          <div key={i} className="card mt-2">
            <div className="grid grid-2">
              <div className="field">
                <label>Group name</label>
                <input value={g.name} onChange={(e) => updateGroup(i, { name: e.target.value })} />
              </div>
              <div className="field">
                <label>Fertilizer type</label>
                <select value={g.fertilizer_type}
                        onChange={(e) => updateGroup(i, { fertilizer_type: e.target.value })}>
                  <option value="natural">Natural</option>
                  <option value="chemical">Chemical</option>
                  <option value="other">Other</option>
                </select>
              </div>
            </div>
            <div className="field">
              <label>Description</label>
              <input value={g.description}
                     onChange={(e) => updateGroup(i, { description: e.target.value })} />
            </div>
            <div className="field">
              <label>Identifier (physical marker)</label>
              <input value={g.identifier}
                     onChange={(e) => updateGroup(i, { identifier: e.target.value })}
                     placeholder="Skull in back right corner" />
            </div>
          </div>
        ))}

        <div className="modal-actions">
          <button onClick={onClose}>Cancel</button>
          <button className="primary" disabled={busy || !form.name.trim()} onClick={submit}>
            {busy ? 'Creating…' : 'Create grow'}
          </button>
        </div>
      </div>
    </div>
  );
}
