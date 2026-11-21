import { useMemo, useState } from 'react';

// Ported from the "Garage Tent Grow Schedule" spreadsheet: a 9-week veg,
// then 12/12 with a harvest window between flower day 55 and 65. Every date
// hangs off the day the seeds popped, which is the one input on this page.

const STORAGE_KEY = 'seedbreed.growSchedule.seedPopped';
const VEG_WEEKS = 9;
const HARVEST_OPENS_DAY = 55;
const HARVEST_CLOSES_DAY = 65;

// lightsOn / lightsOff are 24h hours.
const WEEKS = [
  { phase: 'Seedling', dimmer: 25, ppfd: 200, on: 18, off: 12, hrs: 18, height: 24, notes: 'Keep humidity 65–70%; water lightly around the stem' },
  { phase: 'Seedling', dimmer: 30, ppfd: 250, on: 18, off: 12, hrs: 18, height: 24, notes: 'First true leaves; start light feeding if soil is spent' },
  { phase: 'Early veg', dimmer: 40, ppfd: 350, on: 18, off: 12, hrs: 18, height: 20, notes: '' },
  { phase: 'Early veg', dimmer: 45, ppfd: 400, on: 18, off: 12, hrs: 18, height: 20, notes: 'Top or start LST at 5–6 nodes' },
  { phase: 'Early veg', dimmer: 50, ppfd: 450, on: 18, off: 12, hrs: 18, height: 18, notes: '' },
  { phase: 'Late veg', dimmer: 55, ppfd: 500, on: 18, off: 12, hrs: 18, height: 18, notes: 'Up-pot to final containers if not already' },
  { phase: 'Late veg', dimmer: 60, ppfd: 550, on: 18, off: 12, hrs: 18, height: 16, notes: 'Spread canopy evenly (scrog/LST)' },
  { phase: 'Late veg', dimmer: 65, ppfd: 600, on: 18, off: 12, hrs: 18, height: 16, notes: 'Flip now instead if plants are already 24"+ tall' },
  { phase: 'Late veg', dimmer: 70, ppfd: 600, on: 18, off: 12, hrs: 18, height: 14, notes: 'Lollipop lower third; flip at end of week. Target 20–28" tall' },
  { phase: 'Flower (stretch)', dimmer: 75, ppfd: 650, on: 19, off: 7, hrs: 12, height: 14, notes: '12/12 starts. Expect 1.5–2x stretch; supercrop tall tops' },
  { phase: 'Flower (stretch)', dimmer: 80, ppfd: 700, on: 19, off: 7, hrs: 12, height: 14, notes: '' },
  { phase: 'Flower', dimmer: 90, ppfd: 800, on: 19, off: 7, hrs: 12, height: 12, notes: 'Day 21 defoliation' },
  { phase: 'Flower', dimmer: 100, ppfd: 850, on: 19, off: 7, hrs: 12, height: 12, notes: '' },
  { phase: 'Flower', dimmer: 100, ppfd: 850, on: 19, off: 7, hrs: 12, height: 12, notes: 'Keep RH around 45–50%' },
  { phase: 'Flower', dimmer: 100, ppfd: 850, on: 19, off: 7, hrs: 12, height: 12, notes: '' },
  { phase: 'Flower', dimmer: 100, ppfd: 850, on: 19, off: 7, hrs: 12, height: 12, notes: 'Bleaching or foxtailing at the tops: drop 10% or raise' },
  { phase: 'Flower', dimmer: 100, ppfd: 850, on: 19, off: 7, hrs: 12, height: 12, notes: 'Start checking trichomes around day 50' },
  { phase: 'Harvest window', dimmer: 100, ppfd: 850, on: 19, off: 7, hrs: 12, height: 12, notes: 'Day 55+: harvest when mostly cloudy with some amber' },
  { phase: 'Harvest window', dimmer: 100, ppfd: 850, on: 19, off: 7, hrs: 12, height: 12, notes: 'Harvest by day 65' },
];

const PHASE_CLASS = {
  Seedling: 'seedling',
  'Early veg': 'early-veg',
  'Late veg': 'late-veg',
  'Flower (stretch)': 'stretch',
  Flower: 'flower',
  'Harvest window': 'harvest',
};

// --- dates -----------------------------------------------------------------
// Work in local calendar days only; "YYYY-MM-DD" fed to new Date() is read as
// UTC and can land on the previous day west of Greenwich.

const pad = (n) => String(n).padStart(2, '0');

function toIso(d) {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function parseIso(s) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s || '');
  if (!m) return null;
  const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  return Number.isNaN(d.getTime()) ? null : d;
}

function addDays(d, n) {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
}

function daysBetween(a, b) {
  return Math.round((b - a) / 86400000);
}

const fmtDate = (d) =>
  d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' })
    .replace(/^(\w+),/, '$1');

function fmtHour(h) {
  const suffix = h >= 12 ? 'PM' : 'AM';
  const hr = h % 12 === 0 ? 12 : h % 12;
  return `${hr}:00 ${suffix}`;
}

// --- persistence -----------------------------------------------------------
// Same approach as the infusion calculator: localStorage, per browser.

function readSaved() {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function save(value) {
  try {
    localStorage.setItem(STORAGE_KEY, value);
  } catch {
    /* ignore quota / private-mode errors */
  }
}

function initialDate() {
  const saved = readSaved();
  return parseIso(saved) ? saved : toIso(new Date());
}

// ---------------------------------------------------------------------------

export default function GrowSchedule() {
  const [popped, setPopped] = useState(initialDate);

  const onDateChange = (e) => {
    const v = e.target.value;
    setPopped(v);
    // Only remember a complete, real date; a half-typed one stays on screen.
    if (parseIso(v)) save(v);
  };

  const resetToToday = () => {
    const today = toIso(new Date());
    setPopped(today);
    save(today);
  };

  const plan = useMemo(() => {
    const start = parseIso(popped);
    if (!start) return null;
    const flip = addDays(start, VEG_WEEKS * 7);
    const today = new Date();
    const todayMid = new Date(today.getFullYear(), today.getMonth(), today.getDate());
    const elapsed = daysBetween(start, todayMid);
    const currentWeek = elapsed >= 0 ? Math.floor(elapsed / 7) + 1 : null;

    const rows = WEEKS.map((w, i) => {
      const week = i + 1;
      let flowerDays = '';
      if (week > VEG_WEEKS) {
        const first = (week - VEG_WEEKS - 1) * 7 + 1;
        const last = Math.min(first + 6, HARVEST_CLOSES_DAY);
        flowerDays = `${first}–${last}`;
      }
      return {
        ...w,
        week,
        weekOf: addDays(start, 7 * i),
        dli: Math.round(w.ppfd * w.hrs * 0.0036 * 10) / 10,
        flowerDays,
      };
    });

    return {
      flip,
      opens: addDays(flip, HARVEST_OPENS_DAY - 1),
      closes: addDays(flip, HARVEST_CLOSES_DAY - 1),
      rows,
      currentWeek: currentWeek && currentWeek <= WEEKS.length ? currentWeek : null,
    };
  }, [popped]);

  return (
    <>
      <div className="page-header flex-between">
        <div>
          <div className="eyebrow">Utilities</div>
          <h1>Grow schedule</h1>
        </div>
        <button className="small-btn" onClick={resetToToday}>Today</button>
      </div>

      <p className="muted" style={{ maxWidth: 680 }}>
        A week-by-week light plan for a photoperiod grow: 9 weeks of veg, then 12/12 with a
        harvest window between flower day {HARVEST_OPENS_DAY} and {HARVEST_CLOSES_DAY}. Set the
        day your seeds popped and every other date follows. The date is remembered in this
        browser.
      </p>

      <div className="grid grid-4 mt-6">
        <div className="stat">
          <div className="stat-label">Seeds popped</div>
          <input
            type="date"
            className="schedule-date-input"
            value={popped}
            onChange={onDateChange}
            aria-label="Seeds popped"
          />
        </div>
        <Milestone label={`Flip to 12/12 (after ${VEG_WEEKS}-wk veg)`} date={plan?.flip} />
        <Milestone label={`Harvest opens (flower day ${HARVEST_OPENS_DAY})`} date={plan?.opens} />
        <Milestone label={`Harvest closes (flower day ${HARVEST_CLOSES_DAY})`} date={plan?.closes} />
      </div>

      {!plan ? (
        <div className="empty">
          <div className="empty-title">Pick a date</div>
          Enter the day your seeds popped to build the schedule.
        </div>
      ) : (
        <div className="schedule-wrap mt-6">
          <table className="schedule-table">
            <thead>
              <tr>
                <th className="num">Week</th>
                <th>Week of</th>
                <th>Phase</th>
                <th className="num">Dimmer %</th>
                <th className="num">Target PPFD</th>
                <th className="num">Lights on</th>
                <th className="num">Lights off</th>
                <th className="num">Light hrs</th>
                <th className="num">Height above<br />canopy (in)</th>
                <th className="num">DLI<br />(mol/m²/day)</th>
                <th className="num">Flower day</th>
                <th>Notes</th>
              </tr>
            </thead>
            <tbody>
              {plan.rows.map((r) => (
                <tr key={r.week} className={r.week === plan.currentWeek ? 'current' : undefined}>
                  <td className="num nowrap">
                    {r.week}
                    {r.week === plan.currentWeek && <span className="schedule-now">now</span>}
                  </td>
                  <td className="nowrap">{fmtDate(r.weekOf)}</td>
                  <td>
                    <span className={`phase-pill ${PHASE_CLASS[r.phase]}`}>{r.phase}</span>
                  </td>
                  <td className="num">{r.dimmer}%</td>
                  <td className="num">{r.ppfd}</td>
                  <td className="num nowrap">{fmtHour(r.on)}</td>
                  <td className="num nowrap">{fmtHour(r.off)}</td>
                  <td className="num">{r.hrs}</td>
                  <td className="num">{r.height}</td>
                  <td className="num">{r.dli}</td>
                  <td className="num nowrap">{r.flowerDays}</td>
                  <td className="schedule-notes">{r.notes}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

function Milestone({ label, date }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className="stat-value schedule-milestone">{date ? fmtDate(date) : '—'}</div>
    </div>
  );
}
