import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api } from '../api.js';

export default function StrainDetail() {
  const { id } = useParams();
  const [strain, setStrain] = useState(null);
  const [lineage, setLineage] = useState(null);
  const [seeds, setSeeds] = useState([]);

  useEffect(() => {
    api.get(`/api/strains/${id}`).then(setStrain);
    api.get(`/api/strains/${id}/lineage`).then(setLineage);
    api.get('/api/seeds').then((all) => setSeeds(all.filter((s) => s.strain_id === parseInt(id))));
  }, [id]);

  if (!strain) return <div className="muted">Loading…</div>;

  return (
    <>
      <div className="page-header">
        <div className="eyebrow">
          <Link to="/strains" style={{ color: 'inherit' }}>← All strains</Link>
        </div>
        <h1>{strain.name}</h1>
        <div className="mono small muted">
          {strain.type || 'unknown type'}
          {strain.breeder ? ` · ${strain.breeder}` : ''}
          {strain.indica_pct != null ? ` · ${strain.indica_pct}% indica` : ''}
          {strain.sativa_pct != null ? ` · ${strain.sativa_pct}% sativa` : ''}
          {strain.thc_pct != null ? ` · ${strain.thc_pct}% THC` : ''}
        </div>
        {strain.notes && <p className="mt-4" style={{ maxWidth: 720 }}>{strain.notes}</p>}
      </div>

      <div className="grid grid-2">
        <div className="card">
          <div className="card-title">Lineage</div>
          {lineage && (lineage.parent_a || lineage.parent_b)
            ? <LineageTree node={lineage} />
            : <div className="muted small">No recorded parents — this is a root strain in your library.</div>}
        </div>

        <div className="card">
          <div className="card-title">Seed batches ({seeds.length})</div>
          {seeds.length === 0 ? (
            <div className="muted small">No seed batches recorded for this strain.</div>
          ) : (
            <div className="list">
              {seeds.map((s) => (
                <div key={s.id} className="list-row" style={{ padding: '12px 16px' }}>
                  <div className="list-row-main">
                    <div className="list-row-title">
                      <span className={`badge ${s.origin}`}>{s.origin}</span>
                      <span style={{ marginLeft: 10 }}>
                        {s.quantity != null
                          ? `${s.seeds_remaining ?? s.quantity} of ${s.quantity} remaining`
                          : (s.seeds_remaining != null ? `${s.seeds_remaining} remaining` : 'batch')}
                      </span>
                    </div>
                    <div className="list-row-meta">
                      {s.acquired_date || '—'}
                      {s.source_label ? ` · ${s.source_label}` : ''}
                    </div>
                    {s.notes && <div className="small mt-2">{s.notes}</div>}
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

function LineageTree({ node, prefix = '', isLast = true, isRoot = true }) {
  if (!node) return null;
  const connector = isRoot ? '' : (isLast ? '└─ ' : '├─ ');
  const childPrefix = prefix + (isRoot ? '' : (isLast ? '   ' : '│  '));

  const children = [];
  if (node.parent_a) children.push(node.parent_a);
  if (node.parent_b) children.push(node.parent_b);

  return (
    <div className="tree">
      <div className="tree-node">
        {prefix + connector}
        <Link to={`/strains/${node.id}`} className="tree-name">{node.name}</Link>
        {node.breeder && <span className="tree-meta">— {node.breeder}</span>}
      </div>
      {children.map((c, i) => (
        <LineageTree
          key={c.id + '-' + i}
          node={c}
          prefix={childPrefix}
          isLast={i === children.length - 1}
          isRoot={false}
        />
      ))}
    </div>
  );
}
