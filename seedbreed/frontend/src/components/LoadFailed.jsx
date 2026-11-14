import { Link } from 'react-router-dom';

// Shown by a detail page when its record could not be fetched. A 404 almost
// always means the record was deleted and the URL is stale, so say that
// plainly instead of leaving the page on "Loading…" forever.
export default function LoadFailed({ error, noun, backTo, backLabel }) {
  const gone = error && error.status === 404;
  return (
    <div className="empty card">
      <div className="empty-title">
        {gone ? `This ${noun} no longer exists` : `Couldn’t load this ${noun}`}
      </div>
      <div className="small muted">
        {gone ? 'It was probably deleted. ' : `${error ? error.message : 'Unknown error'}. `}
        <Link to={backTo}>← {backLabel}</Link>
      </div>
    </div>
  );
}
