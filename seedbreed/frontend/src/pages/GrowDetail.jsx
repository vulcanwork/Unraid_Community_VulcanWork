import { useEffect, useState, Fragment } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { api } from '../api.js';

const MAX_PLANTS_PER_GROUP = 4;

export default function GrowDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [grow, setGrow] = useState(null);
  const [plants, setPlants] = useState([]);
  const [strains, setStrains] = useState([]);
  const [checkins, setCheckins] = useState([]);
  const [fert, setFert] = useState([]);
  const [showCheckin, setShowCheckin] = useState(false);
  const [editCheckin, setEditCheckin] = useState(null);
  const [showFert, setShowFert] = useState(false);
  const [editFert, setEditFert] = useState(null);
  const [showEditGrow, setShowEditGrow] = useState(false);
  const [plantModal, setPlantModal] = useState(null); // { group, existing? }

  const load = async () => {
    const [g, p, st, c, f] = await Promise.all([
      api.get(`/api/grows/${id}`),
      api.get(`/api/plants?grow_id=${id}`),
      api.get('/api/strains'),
      api.get(`/api/checkins?grow_id=${id}`),
      api.get(`/api/fertilizer-events?grow_id=${id}`),
    ]);
    setGrow(g); setPlants(p); setStrains(st); setCheckins(c); setFert(f);
  };
  useEffect(() => { load(); }, [id]);

  const deleteFert = async (f) => {
    if (!confirm('Delete this fertilizer event?')) return;
    try { await api.del(`/api/fertilizer-events/${f.id}`); load(); }
    catch (e) { alert(e.message); }
  };
  const deletePlant = async (p) => {
    if (!confirm(`Delete plant "${p.label}" and its photos? This cannot be undone.`)) return;
    try { await api.del(`/api/plants/${p.id}`); load(); }
    catch (e) { alert(e.message); }
  };

  if (!grow) return <div className="muted">Loading…</div>;

  const groupPlants = (gid) => plants.filter((p) => p.group_id === gid);

  return (
    <>
      <div className="page-header">
        <div className="eyebrow">
          <Link to="/grows" style={{ color: 'inherit' }}>← All grows</Link>
        </div>
        <h1>{grow.name}</h1>
        <div className="mono small muted">
          {grow.start_date || '—'} · {grow.location || 'no location'}
        </div>
        {grow.notes && <p className="mt-4" style={{ maxWidth: 720 }}>{grow.notes}</p>}
        <div className="page-actions mt-4">
          <button className="primary" onClick={() => setShowCheckin(true)}>+ Log check-in</button>
          <button onClick={() => setShowFert(true)}>+ Fertilizer event</button>
          <button onClick={() => setShowEditGrow(true)}>Edit grow</button>
        </div>
      </div>

      <h2>Side-by-side</h2>
      <div className="compare">
        {grow.groups.map((group, idx) => (
          <Fragment key={group.id}>
            {idx > 0 && <div className="compare-divider"></div>}
            <GroupPanel
              group={group}
              plants={groupPlants(group.id)}
              onAddPlant={() => setPlantModal({ group })}
              onEditPlant={(p) => setPlantModal({ group, existing: p })}
              onDeletePlant={deletePlant}
            />
          </Fragment>
        ))}
      </div>

      <h2 className="mt-6">Check-ins ({checkins.length})</h2>
      {checkins.length === 0 ? (
        <div className="empty card">
          <div className="empty-title">No check-ins yet</div>
          <div className="small muted">Log your first observation above.</div>
        </div>
      ) : (
        <div className="timeline mt-4">
          {checkins.map((c) => (
            <div key={c.id} className="timeline-item">
              <div className="timeline-item-head">
                <div className="timeline-date">{c.date} · {c.plant_label || 'Whole grow'}</div>
                <div className="row-actions">
                  <button className="small-btn" onClick={() => setEditCheckin(c)}>Edit</button>
                </div>
              </div>
              {c.height_inches && <div className="small mono">height: {c.height_inches}″</div>}
              <div className="mt-2" style={{ whiteSpace: 'pre-wrap' }}>{c.notes}</div>
              {c.photos?.length > 0 && (
                <div className="photo-grid mt-4">
                  {c.photos.map((ph) => (
                    <a key={ph.id} href={`/photos/${ph.filename}`} target="_blank" rel="noopener noreferrer">
                      <img src={`/photos/${ph.filename}`} alt={ph.caption || ''} />
                    </a>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      <h2 className="mt-6">Fertilizer log ({fert.length})</h2>
      {fert.length === 0 ? (
        <div className="empty card">
          <div className="empty-title">No fertilizer events logged</div>
        </div>
      ) : (
        <div className="list">
          {fert.map((f) => {
            const g = grow.groups.find((x) => x.id === f.group_id);
            return (
              <div key={f.id} className="list-row">
                <div className="list-row-main">
                  <div className="list-row-title">{f.product}</div>
                  <div className="list-row-meta">
                    {f.date}
                    {g ? ` · ${g.name}` : ''}
                    {f.stage ? ` · ${f.stage}` : ''}
                    {f.amount ? ` · ${f.amount}` : ''}
                  </div>
                  {f.notes && <div className="small mt-2">{f.notes}</div>}
                </div>
                <div className="row-actions">
                  <button className="small-btn" onClick={() => setEditFert(f)}>Edit</button>
                  <button className="small-btn danger" onClick={() => deleteFert(f)}>Delete</button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {(showCheckin || editCheckin) && (
        <CheckInModal
          grow={grow}
          plants={plants}
          existing={editCheckin}
          onClose={() => { setShowCheckin(false); setEditCheckin(null); }}
          onSaved={() => { setShowCheckin(false); setEditCheckin(null); load(); }}
        />
      )}
      {(showFert || editFert) && (
        <FertilizerModal
          grow={grow}
          existing={editFert}
          onClose={() => { setShowFert(false); setEditFert(null); }}
          onSaved={() => { setShowFert(false); setEditFert(null); load(); }}
        />
      )}
      {showEditGrow && (
        <GrowEditModal
          grow={grow}
          onClose={() => setShowEditGrow(false)}
          onSaved={() => { setShowEditGrow(false); load(); }}
          onDeleted={() => navigate('/grows')}
        />
      )}
      {plantModal && (
        <PlantModal
          grow={grow}
          group={plantModal.group}
          existing={plantModal.existing}
          strains={strains}
          plantsInGroup={groupPlants(plantModal.group.id)}
          onClose={() => setPlantModal(null)}
          onSaved={() => { setPlantModal(null); load(); }}
        />
      )}
    </>
  );
}

function GroupPanel({ group, plants, onAddPlant, onEditPlant, onDeletePlant }) {
  const full = plants.length >= MAX_PLANTS_PER_GROUP;
  return (
    <div className="card">
      <div className="flex-between mb-2">
        <h3 style={{ margin: 0 }}>{group.name}</h3>
        {group.fertilizer_type && (
          <span className={`badge ${group.fertilizer_type}`}>{group.fertilizer_type}</span>
        )}
      </div>
      {group.identifier && (
        <div className="small muted mono">📍 {group.identifier}</div>
      )}
      {group.description && <p className="small mt-2">{group.description}</p>}
      <div className="mt-4">
        <div className="flex-between mb-2">
          <div className="eyebrow">Plants ({plants.length}/{MAX_PLANTS_PER_GROUP})</div>
          <button className="small-btn" disabled={full} onClick={onAddPlant}
                  title={full ? 'Group is full (max 4 plants)' : 'Add a plant'}>
            + Add plant
          </button>
        </div>
        {plants.length === 0 ? (
          <div className="muted small">No plants yet</div>
        ) : (
          plants.map((p) => (
            <div key={p.id} className="plant-item">
              <div className="flex-between">
                <div>
                  <strong>{p.label}</strong>
                  {p.strain_name && <span className="muted"> · {p.strain_name}</span>}
                </div>
                <div className="row-actions">
                  <button className="small-btn" onClick={() => onEditPlant(p)}>Edit</button>
                  <button className="small-btn danger" onClick={() => onDeletePlant(p)}>Delete</button>
                </div>
              </div>
              {p.quantity_harvested && (
                <div className="small mt-2"><span className="muted">Harvested:</span> {p.quantity_harvested}</div>
              )}
              {p.comments && (
                <div className="small mt-2"><span className="muted">Comments:</span> {p.comments}</div>
              )}
              {p.issues && (
                <div className="small mt-2"><span className="muted">Issues:</span> {p.issues}</div>
              )}
              {p.photos?.length > 0 && (
                <div className="photo-grid mt-2">
                  {p.photos.map((ph) => (
                    <a key={ph.id} href={`/photos/${ph.filename}`} target="_blank" rel="noopener noreferrer">
                      <img src={`/photos/${ph.filename}`} alt={ph.caption || ''} />
                    </a>
                  ))}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function CheckInModal({ grow, plants, existing, onClose, onSaved }) {
  const isEdit = !!existing;
  const [form, setForm] = useState(() => existing ? {
    target: existing.plant_id ? 'plant' : 'grow',
    plant_id: existing.plant_id ? String(existing.plant_id) : '',
    height_inches: existing.height_inches ?? '',
    notes: existing.notes || '',
    date: existing.date || '',
  } : {
    target: 'grow', plant_id: '', height_inches: '', notes: '', date: '',
  });
  const [files, setFiles] = useState([]);
  const [photos, setPhotos] = useState(existing?.photos || []);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    try {
      const payload = {
        notes: form.notes,
        height_inches: form.height_inches ? parseFloat(form.height_inches) : null,
      };
      // Send both target keys so switching plant<->grow clears the other side.
      if (form.target === 'plant' && form.plant_id) {
        payload.plant_id = parseInt(form.plant_id);
        payload.grow_id = null;
      } else {
        payload.grow_id = grow.id;
        payload.plant_id = null;
      }

      let checkinId;
      if (isEdit) {
        if (form.date) payload.date = form.date;
        await api.patch(`/api/checkins/${existing.id}`, payload);
        checkinId = existing.id;
      } else {
        const checkin = await api.post('/api/checkins', payload);
        checkinId = checkin.id;
      }

      for (const f of files) {
        const fd = new FormData();
        fd.append('file', f);
        await api.upload(`/api/checkins/${checkinId}/photos`, fd);
      }
      onSaved();
    } catch (e) {
      alert(e.message);
      setBusy(false);
    }
  };

  const removePhoto = async (photo) => {
    if (!confirm('Delete this photo?')) return;
    try {
      await api.del(`/api/photos/${photo.id}`);
      setPhotos((prev) => prev.filter((p) => p.id !== photo.id));
    } catch (e) { alert(e.message); }
  };

  const deleteCheckin = async () => {
    if (!confirm('Delete this check-in and its photos? This cannot be undone.')) return;
    setBusy(true);
    try {
      await api.del(`/api/checkins/${existing.id}`);
      onSaved();
    } catch (e) { alert(e.message); setBusy(false); }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>{isEdit ? 'Edit check-in' : 'Log check-in'}</h2>

        <div className="field">
          <label>What are you checking on?</label>
          <select value={form.target} onChange={(e) => setForm({ ...form, target: e.target.value })}>
            <option value="grow">Whole grow</option>
            <option value="plant">Specific plant</option>
          </select>
        </div>

        {form.target === 'plant' && (
          <div className="field">
            <label>Plant</label>
            <select value={form.plant_id} onChange={(e) => setForm({ ...form, plant_id: e.target.value })}>
              <option value="">— Select —</option>
              {plants.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label} {p.group_name ? `(${p.group_name})` : ''}
                </option>
              ))}
            </select>
          </div>
        )}

        {isEdit && (
          <div className="field">
            <label>Date</label>
            <input type="date" value={form.date}
                   onChange={(e) => setForm({ ...form, date: e.target.value })} />
          </div>
        )}

        <div className="field">
          <label>Height (inches, optional)</label>
          <input type="number" step="0.1" value={form.height_inches}
                 onChange={(e) => setForm({ ...form, height_inches: e.target.value })} />
        </div>

        <div className="field">
          <label>Notes</label>
          <textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })}
                    placeholder="What did you observe? Color, growth, anything notable…" />
        </div>

        {isEdit && photos.length > 0 && (
          <div className="field">
            <label>Current photos</label>
            <div className="photo-grid">
              {photos.map((ph) => (
                <div key={ph.id} className="photo-thumb">
                  <img src={`/photos/${ph.filename}`} alt={ph.caption || ''} />
                  <button type="button" className="photo-remove" title="Remove photo"
                          onClick={() => removePhoto(ph)}>×</button>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="field">
          <label>{isEdit ? 'Add more photos' : 'Photos (optional)'}</label>
          <input type="file" accept="image/*" multiple capture="environment"
                 onChange={(e) => setFiles(Array.from(e.target.files))} />
          {files.length > 0 && <div className="small muted mt-2">{files.length} file(s) selected</div>}
        </div>

        <div className="modal-actions flex-between">
          <div>
            {isEdit && (
              <button className="danger" disabled={busy} onClick={deleteCheckin}>Delete</button>
            )}
          </div>
          <div className="row-actions">
            <button onClick={onClose}>Cancel</button>
            <button className="primary" disabled={busy || !form.notes.trim()} onClick={submit}>
              {busy ? 'Saving…' : isEdit ? 'Save changes' : 'Save check-in'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function GrowEditModal({ grow, onClose, onSaved, onDeleted }) {
  const [form, setForm] = useState({
    name: grow.name || '',
    start_date: grow.start_date || '',
    end_date: grow.end_date || '',
    location: grow.location || '',
    notes: grow.notes || '',
  });
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    try {
      await api.patch(`/api/grows/${grow.id}`, {
        ...form,
        start_date: form.start_date || null,
        end_date: form.end_date || null,
      });
      onSaved();
    } catch (e) { alert(e.message); setBusy(false); }
  };

  const remove = async () => {
    if (!confirm(
      'Delete this entire grow? This removes its groups, plants, check-ins, ' +
      'fertilizer events, and photos. This cannot be undone.'
    )) return;
    setBusy(true);
    try {
      await api.del(`/api/grows/${grow.id}`);
      onDeleted();
    } catch (e) { alert(e.message); setBusy(false); }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>Edit grow</h2>
        <div className="field">
          <label>Name</label>
          <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </div>
        <div className="grid grid-2">
          <div className="field">
            <label>Start date</label>
            <input type="date" value={form.start_date}
                   onChange={(e) => setForm({ ...form, start_date: e.target.value })} />
          </div>
          <div className="field">
            <label>End date</label>
            <input type="date" value={form.end_date}
                   onChange={(e) => setForm({ ...form, end_date: e.target.value })} />
          </div>
        </div>
        <div className="field">
          <label>Location</label>
          <input value={form.location}
                 onChange={(e) => setForm({ ...form, location: e.target.value })} />
        </div>
        <div className="field">
          <label>Notes</label>
          <textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
        </div>
        <div className="modal-actions flex-between">
          <button className="danger" disabled={busy} onClick={remove}>Delete grow</button>
          <div className="row-actions">
            <button onClick={onClose}>Cancel</button>
            <button className="primary" disabled={busy || !form.name.trim()} onClick={submit}>
              {busy ? 'Saving…' : 'Save changes'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function PlantModal({ grow, group, existing, strains, plantsInGroup, onClose, onSaved }) {
  const isEdit = !!existing;
  const [form, setForm] = useState(() => existing ? {
    label: existing.label || '',
    strain_id: existing.strain_id ? String(existing.strain_id) : '',
    quantity_harvested: existing.quantity_harvested || '',
    comments: existing.comments || '',
    issues: existing.issues || '',
  } : {
    label: '', strain_id: '', quantity_harvested: '', comments: '', issues: '',
  });
  const [files, setFiles] = useState([]);
  const [photos, setPhotos] = useState(existing?.photos || []);
  const [busy, setBusy] = useState(false);

  // Block creating a 5th plant before hitting the server.
  const groupFull = !isEdit && plantsInGroup.length >= MAX_PLANTS_PER_GROUP;

  const submit = async () => {
    setBusy(true);
    try {
      const payload = {
        label: form.label,
        strain_id: form.strain_id ? parseInt(form.strain_id) : null,
        quantity_harvested: form.quantity_harvested || null,
        comments: form.comments || null,
        issues: form.issues || null,
      };
      let plantId;
      if (isEdit) {
        await api.patch(`/api/plants/${existing.id}`, payload);
        plantId = existing.id;
      } else {
        const plant = await api.post('/api/plants', {
          ...payload,
          grow_id: grow.id,
          group_id: group.id,
        });
        plantId = plant.id;
      }
      for (const f of files) {
        const fd = new FormData();
        fd.append('file', f);
        await api.upload(`/api/plants/${plantId}/photos`, fd);
      }
      onSaved();
    } catch (e) { alert(e.message); setBusy(false); }
  };

  const removePhoto = async (photo) => {
    if (!confirm('Delete this photo?')) return;
    try {
      await api.del(`/api/plant-photos/${photo.id}`);
      setPhotos((prev) => prev.filter((p) => p.id !== photo.id));
    } catch (e) { alert(e.message); }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>{isEdit ? 'Edit plant' : `Add plant to ${group.name}`}</h2>

        <div className="grid grid-2">
          <div className="field">
            <label>Label</label>
            <input value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })}
                   placeholder="e.g. Black Patronus (left)" />
          </div>
          <div className="field">
            <label>Strain</label>
            <select value={form.strain_id} onChange={(e) => setForm({ ...form, strain_id: e.target.value })}>
              <option value="">— Select strain —</option>
              {strains.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
        </div>

        <div className="field">
          <label>Quantity harvested</label>
          <input value={form.quantity_harvested}
                 onChange={(e) => setForm({ ...form, quantity_harvested: e.target.value })}
                 placeholder="e.g. 3 oz, 85 g, 1 plant" />
        </div>
        <div className="field">
          <label>Comments</label>
          <textarea value={form.comments} onChange={(e) => setForm({ ...form, comments: e.target.value })} />
        </div>
        <div className="field">
          <label>Issues</label>
          <textarea value={form.issues} onChange={(e) => setForm({ ...form, issues: e.target.value })}
                    placeholder="Pests, deficiencies, anything that went wrong…" />
        </div>

        {isEdit && photos.length > 0 && (
          <div className="field">
            <label>Current photos</label>
            <div className="photo-grid">
              {photos.map((ph) => (
                <div key={ph.id} className="photo-thumb">
                  <img src={`/photos/${ph.filename}`} alt={ph.caption || ''} />
                  <button type="button" className="photo-remove" title="Remove photo"
                          onClick={() => removePhoto(ph)}>×</button>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="field">
          <label>{isEdit ? 'Add more photos' : 'Photos (optional)'}</label>
          <input type="file" accept="image/*" multiple capture="environment"
                 onChange={(e) => setFiles(Array.from(e.target.files))} />
          {files.length > 0 && <div className="small muted mt-2">{files.length} file(s) selected</div>}
        </div>

        <div className="modal-actions">
          <button onClick={onClose}>Cancel</button>
          <button className="primary" disabled={busy || !form.label.trim() || groupFull} onClick={submit}>
            {busy ? 'Saving…' : isEdit ? 'Save changes' : 'Add plant'}
          </button>
        </div>
        {groupFull && <p className="small" style={{ color: 'var(--copper-dark)' }}>This group is full (max {MAX_PLANTS_PER_GROUP} plants).</p>}
      </div>
    </div>
  );
}

function FertilizerModal({ grow, existing, onClose, onSaved }) {
  const isEdit = !!existing;
  const [form, setForm] = useState(() => existing ? {
    date: existing.date || '',
    group_id: existing.group_id ? String(existing.group_id) : '',
    product: existing.product || '',
    amount: existing.amount || '',
    stage: existing.stage ?? '',
    notes: existing.notes || '',
  } : {
    date: '', group_id: '', product: '', amount: '', stage: 'veg', notes: '',
  });
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    try {
      const payload = {
        date: form.date || null,
        group_id: form.group_id ? parseInt(form.group_id) : null,
        product: form.product,
        amount: form.amount || null,
        stage: form.stage || null,
        notes: form.notes || null,
      };
      if (isEdit) {
        await api.patch(`/api/fertilizer-events/${existing.id}`, payload);
      } else {
        await api.post('/api/fertilizer-events', { grow_id: grow.id, ...payload });
      }
      onSaved();
    } catch (e) { alert(e.message); setBusy(false); }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>{isEdit ? 'Edit fertilizer event' : 'Fertilizer event'}</h2>
        <div className="grid grid-2">
          <div className="field">
            <label>Date</label>
            <input type="date" value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} />
          </div>
          <div className="field">
            <label>Group</label>
            <select value={form.group_id} onChange={(e) => setForm({ ...form, group_id: e.target.value })}>
              <option value="">— Whole grow —</option>
              {grow.groups.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
            </select>
          </div>
        </div>
        <div className="field">
          <label>Product</label>
          <input value={form.product} onChange={(e) => setForm({ ...form, product: e.target.value })}
                 placeholder="Fox Farm Happy Frog All-Purpose" />
        </div>
        <div className="grid grid-2">
          <div className="field">
            <label>Amount</label>
            <input value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })}
                   placeholder="2 tbsp / 1 cup / 1 tsp per gal" />
          </div>
          <div className="field">
            <label>Stage</label>
            <select value={form.stage} onChange={(e) => setForm({ ...form, stage: e.target.value })}>
              <option value="veg">Veg</option>
              <option value="flower">Flower</option>
              <option value="">Other</option>
            </select>
          </div>
        </div>
        <div className="field">
          <label>Notes</label>
          <textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
        </div>
        <div className="modal-actions">
          <button onClick={onClose}>Cancel</button>
          <button className="primary" disabled={busy || !form.product.trim()} onClick={submit}>
            {busy ? 'Saving…' : isEdit ? 'Save changes' : 'Log event'}
          </button>
        </div>
      </div>
    </div>
  );
}
