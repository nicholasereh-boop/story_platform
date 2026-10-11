// One place for "loading / error + Retry / empty / content" so every public page behaves the same.
//
//   query      a TanStack Query result
//   skeleton   what to show while loading
//   isEmpty    (data) => boolean  -> show `empty`
//   notFound   when set and the server answered 404, show this instead of the error box
//   children   (data) => node
export default function QueryState({ query, skeleton, empty, isEmpty, notFound, children }) {
  if (query.isLoading) {
    return <div role="status" aria-label="Loading">{skeleton}</div>;
  }
  if (query.isError) {
    if (notFound && query.error?.status === 404) return notFound;
    return (
      <div className="notice error" role="alert">
        <p>{query.error?.friendly || "Something went wrong."}</p>
        <button type="button" className="btn secondary small" onClick={() => query.refetch()}>
          Try again
        </button>
      </div>
    );
  }
  if (isEmpty && isEmpty(query.data)) return empty;
  return children(query.data);
}
