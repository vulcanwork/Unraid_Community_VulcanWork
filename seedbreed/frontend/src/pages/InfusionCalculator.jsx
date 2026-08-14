import { useEffect, useMemo, useState } from 'react';

// Ported from SeedBreed.Core/InfusionCalculator.cs
// Post-decarboxylation yield is a fixed efficiency factor applied to all infusions.
const POST_DECARB_YIELD = 0.877;

// Vesicle (fat/solvent) density-based retention factors, keyed by name.
const VESICLES = {
  Avocado: 0.787,
  Coconut: 0.858,
  Olive: 0.823,
  Butter: 0.889,
  '190 Proof': 0.95,
  'Bacon Fat': 0.667,
  Grapeseed: 0.81,
  MTC: 0.9,
  Walnut: 0.83,
};

const STORAGE_KEY = 'seedbreed.infusionCalculator';

const DEFAULTS = {
  gramsCannabis: '5',
  percentThc: '',
  percentCbd: '',
  vesicle: '',
  mlVesicle: '',
  mlUsed: '',
  totalServings: '',
};

const num = (v) => {
  const n = parseFloat(v);
  return Number.isFinite(n) ? n : 0;
};

const fmt = (n) => (Number.isFinite(n) ? Math.round(n * 10) / 10 : 0);

function loadSaved() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? { ...DEFAULTS, ...JSON.parse(raw) } : DEFAULTS;
  } catch {
    return DEFAULTS;
  }
}

export default function InfusionCalculator() {
  const [form, setForm] = useState(loadSaved);

  // Persist inputs so they're restored on the next visit.
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(form));
    } catch {
      /* ignore quota / private-mode errors */
    }
  }, [form]);

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));

  const r = useMemo(() => {
    const grams = num(form.gramsCannabis);
    const thc = num(form.percentThc);
    const cbd = num(form.percentCbd);
    const yield_ = form.vesicle ? VESICLES[form.vesicle] : 0;
    const ml = num(form.mlVesicle);
    const used = num(form.mlUsed);
    const servings = num(form.totalServings);

    // Convert grams of flower → mg of cannabinoid: grams × (percent / 100) × 1000.
    const mgThcInfused = grams * (thc / 100) * 1000 * POST_DECARB_YIELD * yield_;
    const mgCbdInfused = grams * (cbd / 100) * 1000 * POST_DECARB_YIELD * yield_;

    const mgPerMlThc = mgThcInfused === 0 || ml === 0 ? 0 : mgThcInfused / ml;
    const mgPerMlCbd = mgCbdInfused === 0 || ml === 0 ? 0 : mgCbdInfused / ml;

    // Total cannabinoid in the finished recipe = potency × oil actually used.
    const mgThcTotal = mgPerMlThc * used;
    const mgCbdTotal = mgPerMlCbd * used;

    // Per serving = recipe total split across the number of servings.
    const mgThcPerServing = servings === 0 ? 0 : mgThcTotal / servings;
    const mgCbdPerServing = servings === 0 ? 0 : mgCbdTotal / servings;

    return {
      mgThcInfused, mgCbdInfused, mgPerMlThc, mgPerMlCbd,
      mgThcPerServing, mgCbdPerServing, mgThcTotal, mgCbdTotal,
    };
  }, [form]);

  return (
    <>
      <div className="page-header flex-between">
        <div>
          <div className="eyebrow">Utilities</div>
          <h1>Infusion calculator</h1>
        </div>
        <button className="small-btn" onClick={() => setForm(DEFAULTS)}>Reset</button>
      </div>

      <p className="muted" style={{ maxWidth: 640 }}>
        Estimate cannabinoid potency for an oil or alcohol infusion, then break it down per
        recipe and per serving. Adjust the inputs and the results update live — your entries are
        saved for next time.
      </p>

      <div className="grid grid-2 mt-6">
        <div className="card">
          <div className="card-title">Inputs</div>

          <div className="grid grid-2">
            <div className="field">
              <label>Cannabis (g)</label>
              <input type="number" min="0" value={form.gramsCannabis}
                     onChange={set('gramsCannabis')} />
            </div>
            <div className="field">
              <label>Vesicle</label>
              <select value={form.vesicle} onChange={set('vesicle')}>
                <option value="">— Select —</option>
                {Object.keys(VESICLES).map((v) => (
                  <option key={v} value={v}>{v}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-2">
            <div className="field">
              <label>THC %</label>
              <input type="number" min="0" value={form.percentThc}
                     onChange={set('percentThc')} />
            </div>
            <div className="field">
              <label>CBD %</label>
              <input type="number" min="0" value={form.percentCbd}
                     onChange={set('percentCbd')} />
            </div>
          </div>

          <div className="field">
            <label>Oil / solvent (ml)</label>
            <input type="number" min="0" value={form.mlVesicle}
                   onChange={set('mlVesicle')} />
          </div>

          <div className="card-title" style={{ marginTop: 8 }}>Used in recipe</div>
          <div className="grid grid-2">
            <div className="field">
              <label>ml used</label>
              <input type="number" min="0" value={form.mlUsed}
                     onChange={set('mlUsed')} />
            </div>
            <div className="field">
              <label>Total servings</label>
              <input type="number" min="0" value={form.totalServings}
                     onChange={set('totalServings')} />
            </div>
          </div>
        </div>

        <div>
          <h2 className="mt-4">Infused potency</h2>
          <div className="grid grid-2">
            <Result label="Infused THC (mg)" value={fmt(r.mgThcInfused)} />
            <Result label="Infused CBD (mg)" value={fmt(r.mgCbdInfused)} />
            <Result label="THC mg/ml" value={fmt(r.mgPerMlThc)} />
            <Result label="CBD mg/ml" value={fmt(r.mgPerMlCbd)} />
          </div>

          <h2 className="mt-6">Per serving</h2>
          <div className="grid grid-2">
            <Result label="THC / serving (mg)" value={fmt(r.mgThcPerServing)} />
            <Result label="CBD / serving (mg)" value={fmt(r.mgCbdPerServing)} />
            <Result label="THC total (mg)" value={fmt(r.mgThcTotal)} />
            <Result label="CBD total (mg)" value={fmt(r.mgCbdTotal)} />
          </div>
        </div>
      </div>
    </>
  );
}

function Result({ label, value }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
    </div>
  );
}
