import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { deleteStory, listStories, storyAction } from "../../api";
import ConfirmDialog from "../../components/ConfirmDialog";
import Pagination from "../../components/Pagination";
import StatusBadge from "../../components/StatusBadge";
import { fmtDate, num } from "../../utils/format";

const TABS = [
  { value: "", label: "All" },
  { value: "draft", label: "Draft" },
  { value: "scheduled", label: "Scheduled" },
  { value: "published", label: "Published" },
  { value: "archived", label: "Archived" },
];

export default function StoryListPage() {
  const queryClient = useQueryClient();
  // Filters live in the URL so a refresh or a shared link keeps them.
  const [params, setParams] = useSearchParams();
  const status = params.get("status") || "";
  const q = params.get("q") || "";
  const page = Number(params.get("page")) || 1;

  const [search, setSearch] = useState(q);
  const [toDelete, setToDelete] = useState(null);
  const [actionError, setActionError] = useState("");

  const update = (changes) => {
    const next = new URLSearchParams(params);
    Object.entries(changes).forEach(([k, v]) => (v ? next.set(k, v) : next.delete(k)));
    setParams(next, { replace: true });
  };

  // Search runs 300 ms after typing stops and goes back to page 1.
  useEffect(() => {
    const t = setTimeout(() => {
      if (search.trim() !== q) update({ q: search.trim(), page: "" });
    }, 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ["stories", { status, q, page }],
    queryFn: () => listStories({ status: status || undefined, q: q || undefined, page }),
    placeholderData: (prev) => prev,
  });

  const done = () => queryClient.invalidateQueries({ queryKey: ["stories"] });
  const act = useMutation({
    mutationFn: ({ id, action }) => storyAction(id, action),
    onSuccess: () => { setActionError(""); done(); },
    onError: (err) => setActionError(err.friendly),
  });
  const remove = useMutation({
    mutationFn: (id) => deleteStory(id),
    onSuccess: () => { setToDelete(null); setActionError(""); done(); },
    onError: (err) => { setToDelete(null); setActionError(err.friendly); },
  });

  const items = data?.items || [];

  return (
    <>
      <div className="row wrap">
        <h1 className="grow">Stories</h1>
        <Link className="btn" to="/admin/stories/new">New story</Link>
      </div>

      <div className="row wrap">
        <div className="tabs" role="tablist" aria-label="Filter by status">
          {TABS.map((tab) => (
            <button
              key={tab.value || "all"}
              type="button"
              role="tab"
              aria-selected={status === tab.value}
              className={status === tab.value ? "active" : undefined}
              onClick={() => update({ status: tab.value, page: "" })}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <div className="field grow">
          <label htmlFor="story-search" className="sr-only">Search stories</label>
          <input id="story-search" type="search" placeholder="Search stories…" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
      </div>

      {actionError && <div className="notice error" role="alert">{actionError}</div>}
      {isLoading && <p className="muted">Loading stories…</p>}
      {isError && (
        <div className="notice error" role="alert">
          {error.friendly} <button type="button" className="btn secondary small" onClick={() => refetch()}>Retry</button>
        </div>
      )}
      {!isLoading && !isError && items.length === 0 && (
        <div className="empty">
          {q || status ? "No stories match these filters." : "No stories yet."}{" "}
          {!q && !status && <Link to="/admin/stories/new">Write your first story</Link>}
        </div>
      )}

      {items.length > 0 && (
        <div className={`table-wrap${isFetching ? " busy" : ""}`}>
          <table className="table">
            <thead>
              <tr>
                <th>Title</th><th>Status</th><th>Categories</th><th>Updated</th>
                <th className="num">Views</th><th className="num">Likes</th><th className="num">Comments</th><th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((s) => (
                <tr key={s.id}>
                  <td><Link to={`/admin/stories/${s.id}/edit`}>{s.title || "(Untitled)"}</Link></td>
                  <td><StatusBadge status={s.status} /></td>
                  <td>{s.categories?.map((c) => c.name).join(", ") || <span className="muted">—</span>}</td>
                  <td>{fmtDate(s.updated_at)}</td>
                  <td className="num">{num(s.view_count)}</td>
                  <td className="num">{num(s.like_count)}</td>
                  <td className="num">{num(s.comment_count)}</td>
                  <td>
                    <div className="row-actions">
                      <Link className="btn secondary small" to={`/admin/stories/${s.id}/edit`}>Edit</Link>
                      <Link className="btn secondary small" to={`/admin/stories/${s.id}/preview`}>Preview</Link>
                      {s.status === "published" ? (
                        <button type="button" className="btn secondary small" disabled={act.isPending} onClick={() => act.mutate({ id: s.id, action: "unpublish" })}>Unpublish</button>
                      ) : (
                        <button type="button" className="btn secondary small" disabled={act.isPending} onClick={() => act.mutate({ id: s.id, action: "publish" })}>Publish</button>
                      )}
                      {s.status !== "archived" && (
                        <button type="button" className="btn secondary small" disabled={act.isPending} onClick={() => act.mutate({ id: s.id, action: "archive" })}>Archive</button>
                      )}
                      <button type="button" className="btn danger small" onClick={() => setToDelete(s)}>Delete</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Pagination pagination={data?.pagination} onPage={(p) => update({ page: p > 1 ? String(p) : "" })} />

      {toDelete && (
        <ConfirmDialog
          title="Delete this story?"
          message={`“${toDelete.title || "Untitled"}” will be deleted. This cannot be undone.`}
          confirmLabel="Delete story"
          danger
          busy={remove.isPending}
          onCancel={() => setToDelete(null)}
          onConfirm={() => remove.mutate(toDelete.id)}
        />
      )}
    </>
  );
}
