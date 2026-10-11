// Previous / Next controls for the server's pagination object {page, total_pages, total_items?}.
export default function Pagination({ pagination, onPage }) {
  if (!pagination || pagination.total_pages <= 1) return null;
  const { page, total_pages: total } = pagination;
  return (
    <nav className="pager" aria-label="Pagination">
      <button type="button" className="btn secondary small" disabled={page <= 1} onClick={() => onPage(page - 1)}>← Previous</button>
      <span aria-live="polite">Page {page} of {total}</span>
      <button type="button" className="btn secondary small" disabled={page >= total} onClick={() => onPage(page + 1)}>Next →</button>
    </nav>
  );
}
