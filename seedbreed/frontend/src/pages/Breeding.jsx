import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { sexBadge } from './GrowDetail.jsx';

const POLLEN_SEXES = new Set(['male', 'hermaphrodite']);

function plantOptionLabel(p) {
  const badge = sexBadge(p.sex);
  return `${p.label}${p.strain_name ? ` — ${p.strain_name}` : ''}${badge ? ` (${badge.symbol} ${badge.text})` : ''}`;
}

function pollenOptionLabel(p) {
  return `${p.source_plant_label || `Plant #${p.source_plant_id}`}`
    + `${p.source_plant_strain_name ? ` — ${p.source_plant_strain_name}` : ''}`
    + ` · ${p.collected_date}`;
}

export default function Breeding() {
  const [events, setEvents] = useState([]);
  const [plants, setPlants] = useState([]);
  const [pollen, setPollen] = useState([]);
  const [showNewEvent, setShowNewEvent] = useState(false);
  const [editEvent, setEditEvent] = useState(null);
  const [showNewPollen, setShowNewPollen] = useState(false);
  const [editPollen, setEditPollen] = useState(null);

  const load = async () => {
    const [e, p, po] = await Promise.all([
      api.get('/api/seed-production'),
      api.get('/api/plants'),
      api.get('/api/pollen'),
    ]);
    setEvents(e); setPlants(p); setPollen(po);
  };
  useEffect(() => { load(); }, []);

  const deletePollen = async (p) => {
    if (!confirm(`Delete pollen from ${p.source_plant_label} (${p.collected_date})?`)) return;
    try {
      await api.del(`/api/pollen/${p.id}`);
      load();
    } catch (e) { alert(e.message); }
  };

  return (
    <>
      <div className="page-header">
        <div className="eyebrow">Crosses & accidents</div>
        <h1>Breeding</h1>
      </div>

      {/* ---- Pollen library ---- */}
      <div className="flex-between mt-6">
        <div>
          <div className="eyebrow">Pollen library</div>
          <h2 style={{ margin: 0 }}>Collected pollen</h2>
        </div>
        <button className="primary" onClick={() => setShowNewPollen(true)}>+ Log pollen collection</button>
      </div>
      <p className="muted" style={{ maxWidth: 640 }}>
        Each time you collect pollen from a male or hermaphrodite plant, log it here. Pick one of
        these records when logging a cross below and the father is filled in automatically.
      </p>

      {pollen.length === 0 ? (
        <div className="empty card mt-4">
          <div className="empty-title">No pollen collected yet</div>
          <div className="small muted">
            Mark a plant male or hermaphrodite (edit it on its grow page), then log a collection.
          </div>
        </div>
      ) : (
        <div className="list mt-4">
          {pollen.map((p) => (
            <div key={p.id} className="list-row">
              <div className="list-row-main">
                <div className="list-row-title">
                  {p.source_plant_label || `Plant #${p.source_plant_id}`}
                  {p.source_plant_strain_name && <span className="muted"> — {p.source_plant_strain_name}</span>}
                </div>
                <div className="list-row-meta">
                  collected {p.collected_date}
                  {p.amount ? ` · ${p.amount}` : ''}
                  {p.storage ? ` · ${p.storage}` : ''}
                </div>
                {p.notes && <div className="small mt-2">{p.notes}</div>}
              </div>
              <div className="row-actions">
                <button className="small-btn" onClick={() => setEditPollen(p)}>Edit</button>
                <button className="small-btn danger" onClick={() => deletePollen(p)}>Delete</button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ---- Seed production ---- */}
      <div className="flex-between" style={{ marginTop: 40 }}>
        <div>
          <div className="eyebrow">Seed production</div>
          <h2 style={{ margin: 0 }}>Crosses & seed events</h2>
        </div>
        <button className="primary" onClick={() => setShowNewEvent(true)}>+ Log seed production</button>
      </div>
      <p className="muted" style={{ maxWidth: 640 }}>
        Anytime a plant produces seeds — intentional cross, accidental pollination, or a hermie —
        log it here. The seeds get linked back to the mother and the pollen used, giving you a full
        genetic trail to follow forward and backward.
      </p>

      {events.length === 0 ? (
        <div className="empty card mt-4">
          <div className="empty-title">No breeding events recorded</div>
          <div className="small muted">Log the first one when seeds show up.</div>
        </div>
      ) : (
        <div className="list mt-4">
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
                  {e.pollen_label ? ` · pollen: ${e.pollen_label}` : ''}
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

      {(showNewPollen || editPollen) && (
        <PollenModal
          plants={plants}
          existing={editPollen}
          onClose={() => { setShowNewPollen(false); setEditPollen(null); }}
          onSaved={() => { setShowNewPollen(false); setEditPollen(null); load(); }}
        />
      )}

      {(showNewEvent || editEvent) && (
        <BreedingModal
          plants={plants}
          pollen={pollen}
          existing={editEvent}
          onClose={() => { setShowNewEvent(false); setEditEvent(null); }}
          onSaved={() => { setShowNewEvent(false); setEditEvent(null); load(); }}
        />
      )}
    </>
  );
}

function PollenModal({ plants, existing, onClose, onSaved }) {
  const isEdit = !!existing;
  const donors = plants.filter((p) => POLLEN_SEXES.has(p.sex));
  const [form, setForm] = useState(() => existing ? {
    source_plant_id: String(existing.source_plant_id),
    collected_date: existing.collected_date || '',
    amount: existing.amount || '',
    storage: existing.storage || '',
    notes: existing.notes || '',
  } : {
    source_plant_id: '', collected_date: '', amount: '', storage: '', notes: '',
  });
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    try {
      const payload = {
        source_plant_id: parseInt(form.source_plant_id),
        collected_date: form.collected_date || null,
        amount: form.amount || null,
        storage: form.storage || null,
        notes: form.notes || null,
      };
      if (isEdit) {
        await api.patch(`/api/pollen/${existing.id}`, payload);
      } else {
        await api.post('/api/pollen', payload);
      }
      onSaved();
    } catch (e) { alert(e.message); setBusy(false); }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>{isEdit ? 'Edit pollen collection' : 'Log pollen collection'}</h2>

        <div className="field">
          <label>Source plant (male or hermaphrodite)</label>
          <select value={form.source_plant_id} disabled={donors.length === 0}
                  onChange={(e) => setForm({ ...form, source_plant_id: e.target.value })}>
            <option value="">— Select plant —</option>
            {donors.map((p) => (
              <option key={p.id} value={p.id}>{plantOptionLabel(p)}</option>
            ))}
          </select>
          {donors.length === 0 && (
            <p className="small muted" style={{ margin: '6px 0 0' }}>
              No plants are marked male or hermaphrodite yet. Edit a plant on its grow page and set its sex first.
            </p>
          )}
        </div>

        <div className="grid grid-2">
          <div className="field">
            <label>Date collected</label>
            <input type="date" value={form.collected_date}
                   onChange={(e) => setForm({ ...form, collected_date: e.target.value })} />
          </div>
          <div className="field">
            <label>Amount</label>
            <input value={form.amount} placeholder="e.g. ~0.5 g, 2 vials"
                   onChange={(e) => setForm({ ...form, amount: e.target.value })} />
          </div>
        </div>

        <div className="field">
          <label>Storage</label>
          <input value={form.storage} placeholder="e.g. freezer, vial #3"
                 onChange={(e) => setForm({ ...form, storage: e.target.value })} />
        </div>

        <div className="field">
          <label>Notes</label>
          <textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
        </div>

        <div className="modal-actions">
          <button onClick={onClose}>Cancel</button>
          <button className="primary" disabled={busy || !form.source_plant_id} onClick={submit}>
            {busy ? 'Saving…' : isEdit ? 'Save changes' : 'Log collection'}
          </button>
        </div>
      </div>
    </div>
  );
}

function BreedingModal({ plants, pollen, existing, onClose, onSaved }) {
  const isEdit = !!existing;
  const [form, setForm] = useState(() => existing ? {
    date: existing.date || '',
    parent_a_plant_id: existing.parent_a_plant_id ? String(existing.parent_a_plant_id) : '',
    pollen_collection_id: existing.pollen_collection_id ? String(existing.pollen_collection_id) : '',
    event_type: existing.event_type || 'intentional_cross',
    seed_count: existing.seed_count ?? '',
    new_strain_name: existing.new_strain_name || '',
    notes: existing.notes || '',
  } : {
    date: '', parent_a_plant_id: '', pollen_collection_id: '',
    event_type: 'intentional_cross', seed_count: '', new_strain_name: '', notes: '',
  });
  const [busy, setBusy] = useState(false);

  // A pre-pollen-tracking event that still carries a manually-picked father.
  const legacyDonor = isEdit && existing.parent_b_label && !existing.pollen_collection_id
    ? existing.parent_b_label : null;

  const submit = async () => {
    setBusy(true);
    try {
      const payload = {
        date: form.date || null,
        parent_a_plant_id: parseInt(form.parent_a_plant_id),
        pollen_collection_id: form.pollen_collection_id ? parseInt(form.pollen_collection_id) : null,
        event_type: form.event_type,
        seed_count: form.seed_count !== '' ? parseInt(form.seed_count) : null,
        new_strain_name: form.new_strain_name || null,
        notes: form.notes || null,
      };
      if (isEdit) {
        // Don't wipe a legacy manual father unless the user actually picked pollen.
        if (legacyDonor && !form.pollen_collection_id) delete payload.pollen_collection_id;
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
              <option key={p.id} value={p.id}>{plantOptionLabel(p)}</option>
            ))}
          </select>
        </div>

        <div className="field">
          <label>Pollen used (sets the father)</label>
          <select value={form.pollen_collection_id}
                  onChange={(e) => setForm({ ...form, pollen_collection_id: e.target.value })}>
            <option value="">— None (self / herm / unknown / not collected) —</option>
            {pollen.map((p) => (
              <option key={p.id} value={p.id}>{pollenOptionLabel(p)}</option>
            ))}
          </select>
          {legacyDonor && !form.pollen_collection_id && (
            <p className="small muted" style={{ margin: '6px 0 0' }}>
              Current pollen donor: {legacyDonor} (no pollen record). Pick a pollen record to replace it.
            </p>
          )}
          {pollen.length === 0 && (
            <p className="small muted" style={{ margin: '6px 0 0' }}>
              No pollen logged yet — add a collection in the Pollen library above to record a father.
            </p>
          )}
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
