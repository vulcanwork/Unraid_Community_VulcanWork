import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api.js';

export default function Dashboard() {
  const [stats, setStats] = useState(null);
  const [grows, setGrows] = useState([]);
  const [recentCheckins, setRecentCheckins] = useState([]);

  useEffect(() => {
    api.get('/api/dashboard').then(setStats);
    api.get('/api/grows').then(setGrows);
    api.get('/api/checkins').then((c) => setRecentCheckins(c.slice(0, 5)));
  }, []);

  return (
    <>
      <div className="page-header">
        <div className="eyebrow">Overview</div>
        <h1>Garden journal</h1>
      </div>

      <div className="grid grid-4">
        {stats && (
          <>
            <StatCard label="Grows"   value={stats.grows} />
            <StatCard label="Plants"  value={stats.plants} />
            <StatCard label="Strains" value={stats.strains} />
            <StatCard label="Crosses" value={stats.crosses} />
          </>
        )}
      </div>

      <div className="grid grid-2 mt-6">
        <div>
          <h2 className="mt-4">Active grows</h2>
          {grows.length === 0 ? (
            <div className="empty card">
              <div className="empty-title">No grows yet</div>
              <div className="small muted">Start one to begin tracking.</div>
            </div>
          ) : (
            <div className="list">
              {grows.map((g) => (
                <Link key={g.id} to={`/grows/${g.id}`} className="list-row">
                  <div className="list-row-main">
                    <div className="list-row-title">{g.name}</div>
                    <div className="list-row-meta">
                      {g.start_date || '—'} · {g.location || 'no location'}
                      {' · '}{g.groups?.length || 0} group{g.groups?.length === 1 ? '' : 's'}
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>

        <div>
          <h2 className="mt-4">Recent check-ins</h2>
          {recentCheckins.length === 0 ? (
            <div className="empty card">
              <div className="empty-title">Nothing logged yet</div>
              <div className="small muted">Open a grow and add a check-in.</div>
            </div>
          ) : (
            <div className="list">
              {recentCheckins.map((c) => (
                <div key={c.id} className="list-row">
                  <div className="list-row-main">
                    <div className="list-row-title">{c.plant_label || 'Whole grow'}</div>
                    <div className="list-row-meta">
                      {c.date}{c.height_inches ? ` · ${c.height_inches}″` : ''}
                    </div>
                    <div className="small mt-2">{truncate(c.notes, 120)}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
}

function StatCard({ label, value }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value ?? '—'}</div>
    </div>
  );
}

function truncate(s, n) {
  if (!s) return '';
  return s.length > n ? s.slice(0, n) + '…' : s;
}
