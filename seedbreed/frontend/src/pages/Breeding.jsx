import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api.js';

export default function Breeding() {
  const [events, setEvents] = useState([]);
  const [plants, setPlants] = useState([]);
  const [showNew, setShowNew] = useState(false);
  const [editEvent, setEditEvent] = useState(null);

  const load = async () => {
    const [e, p] = await Promise.all([
      api.get('/api/seed-production'),
      api.get('/api/plants'),
    ]);
    setEvents(e); setPlants(p);
  };
  useEffect(() => { load(); }, []);

  return (
    <>
      <div className="page-header flex-between">
        <div>
          <div className="eyebrow">Crosses & accidents</div>
          <h1>Breeding</h1>
        </div>
        <button className="primary" onClick={() => setShowNew(true)}>+ Log seed production</button>
      </div>

      <p className="muted" style={{ maxWidth: 640 }}>
        Anytime a plant produces seeds — intentional cross, accidental pollination, or a hermie —
        log it here. The seeds get linked back to their parent plant(s), giving you a full genetic
        trail to follow forward and backward.
      </p>

      {events.length === 0 ? (
        <div className="empty card mt-6">
          <div className="empty-title">No breeding events recorded</div>
          <div className="small muted">Log the first one when seeds show up.</div>
        </div>
      ) : (
        <div className="list mt-6">
          {events.map((e) => (
            <div key={e.id} className="list-row">
              <div className="list-row-main">
                <div className="list-row-title">
                  {e.parent_a_label}
                  {e.parent_b_label ? <span className="muted"> × </span> : ''}
                  {e.parent_b_label || ''}
                  {e.new_strain_name && (
                    <span style={{ marginLeft: 12 }} className="badge produced">
                      → {e.new_strain_name}
                    </span>
                  )}
                </div>
                <div className="list-row-meta">
                  {e.date}
                  {' · '}{e.event_type.replace(/_/g, ' ')}
                  {e.seed_count ? ` · ${e.seed_count} seeds` : ''}
                </div>
                {e.notes && <div className="small mt-2">{e.notes}</div>}
              </div>
              <div className="row-actions">
                <button className="small-btn" onClick={() => setEditEvent(e)}>Edit</button>
              </div>
            </div>
          ))}
        </div>
      )}

      {(showNew || editEvent) && (
        <BreedingModal
          plants={plants}
          existing={editEvent}
          onClose={() => { setShowNew(false); setEditEvent(null); }}
          onSaved={() => { setShowNew(false); setEditEvent(null); load(); }}
        />
      )}
    </>
  );
}

function BreedingModal({ plants, existing, onClose, onSaved }) {
  const isEdit = !!existing;
  const [form, setForm] = useState(() => existing ? {
    date: existing.date || '',
    parent_a_plant_id: existing.parent_a_plant_id ? String(existing.parent_a_plant_id) : '',
    parent_b_plant_id: existing.parent_b_plant_id ? String(existing.parent_b_plant_id) : '',
    event_type: existing.event_type || 'intentional_cross',
    seed_count: existing.seed_count ?? '',
    new_strain_name: existing.new_strain_name || '',
    notes: existing.notes || '',
  } : {
    date: '', parent_a_plant_id: '', parent_b_plant_id: '',
    event_type: 'intentional_cross', seed_count: '', new_strain_name: '', notes: '',
  });
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    try {
      const payload = {
        date: form.date || null,
        parent_a_plant_id: parseInt(form.parent_a_plant_id),
        parent_b_plant_id: form.parent_b_plant_id ? parseInt(form.parent_b_plant_id) : null,
        event_type: form.event_type,
        seed_count: form.seed_count !== '' ? parseInt(form.seed_count) : null,
        new_strain_name: form.new_strain_name || null,
        notes: form.notes || null,
      };
      if (isEdit) {
        await api.patch(`/api/seed-production/${existing.id}`, payload);
      } else {
        await api.post('/api/seed-production', payload);
      }
      onSaved();
    } catch (e) { alert(e.message); setBusy(false); }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>{isEdit ? 'Edit seed production' : 'Log seed production'}</h2>

        <div className="grid grid-2">
          <div className="field">
            <label>Date</label>
            <input type="date" value={form.date}
                   onChange={(e) => setForm({ ...form, date: e.target.value })} />
          </div>
          <div className="field">
            <label>Event type</label>
            <select value={form.event_type}
                    onChange={(e) => setForm({ ...form, event_type: e.target.value })}>
              <option value="intentional_cross">Intentional cross</option>
              <option value="accidental_pollination">Accidental pollination</option>
              <option value="hermaphrodite">Hermaphrodite</option>
              <option value="self_pollinated">Self-pollinated</option>
              <option value="unknown">Unknown</option>
            </select>
          </div>
        </div>

        <div className="field">
          <label>Parent A — mother (seed bearer)</label>
          <select value={form.parent_a_plant_id}
                  onChange={(e) => setForm({ ...form, parent_a_plant_id: e.target.value })}>
            <option value="">— Select plant —</option>
            {plants.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}{p.strain_name ? ` — ${p.strain_name}` : ''}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label>Parent B — pollen donor (optional)</label>
          <select value={form.parent_b_plant_id}
                  onChange={(e) => setForm({ ...form, parent_b_plant_id: e.target.value })}>
            <option value="">— None (self / herm / unknown) —</option>
            {plants.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}{p.strain_name ? ` — ${p.strain_name}` : ''}
              </option>
            ))}
          </select>
        </div>

        <div className="grid grid-2">
          <div className="field">
            <label>Seed count</label>
            <input type="number" value={form.seed_count}
                   onChange={(e) => setForm({ ...form, seed_count: e.target.value })} />
          </div>
          <div className="field">
            <label>New strain name (optional)</label>
            <input value={form.new_strain_name}
                   onChange={(e) => setForm({ ...form, new_strain_name: e.target.value })}
                   placeholder="e.g. Black Panty" />
          </div>
        </div>
        <p className="small muted" style={{ marginTop: -8 }}>
          {isEdit
            ? 'Editing updates this event record only — it won’t create or rename a strain/seed batch.'
            : 'If you name the cross, it auto-creates a strain with both parents linked and adds a seed batch.'}
        </p>

        <div className="field">
          <label>Notes</label>
          <textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
        </div>

        <div className="modal-actions">
          <button onClick={onClose}>Cancel</button>
          <button className="primary" disabled={busy || !form.parent_a_plant_id} onClick={submit}>
            {busy ? 'Saving…' : isEdit ? 'Save changes' : 'Log event'}
          </button>
        </div>
      </div>
    </div>
  );
}
