import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { listMedia, uploadMedia } from "../../api";
import { fieldMessage } from "../../utils/format";
import Pagination from "../Pagination";

// Grid + search + pagination + upload (button and drag-and-drop). Used by the Media page AND the MediaPicker modal.
// `onSelect(asset)` is called when a thumbnail is chosen; `selectedId` highlights one.
export default function MediaLibrary({ onSelect, selectedId = null }) {
  const queryClient = useQueryClient();
  const fileInput = useRef(null);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [dragging, setDragging] = useState(false);
  const [uploads, setUploads] = useState([]); // [{id, name, status: uploading|done|error, error}]

  // Search runs 300 ms after typing stops.
  useEffect(() => {
    const t = setTimeout(() => {
      setQ(search.trim());
      setPage(1);
    }, 300);
    return () => clearTimeout(t);
  }, [search]);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["media", { page, q }],
    queryFn: () => listMedia({ page, q: q || undefined }),
    placeholderData: (prev) => prev,
  });

  // Files go up ONE AT A TIME so every file gets its own success or error message
  // (the server rejects a whole request if any file in it is invalid).
  const upload = async (fileList) => {
    const files = Array.from(fileList || []);
    if (!files.length) return;
    const batch = files.map((f, i) => ({ id: `${Date.now()}-${i}`, name: f.name, status: "uploading", error: "" }));
    setUploads((prev) => [...batch, ...prev].slice(0, 12));
    for (let i = 0; i < files.length; i += 1) {
      const entry = batch[i];
      try {
        await uploadMedia([files[i]]);
        setUploads((prev) => prev.map((u) => (u.id === entry.id ? { ...u, status: "done" } : u)));
      } catch (err) {
        const message = fieldMessage(err, "file", "files", "detail") || err.friendly;
        setUploads((prev) => prev.map((u) => (u.id === entry.id ? { ...u, status: "error", error: message } : u)));
      }
    }
    setPage(1);
    queryClient.invalidateQueries({ queryKey: ["media"] });
  };

  const onDrop = (event) => {
    event.preventDefault();
    setDragging(false);
    upload(event.dataTransfer.files);
  };

  const busy = uploads.some((u) => u.status === "uploading");
  const items = data?.items || [];

  return (
    <div
      className={`media-lib${dragging ? " dragging" : ""}`}
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget)) setDragging(false); }}
      onDrop={onDrop}
    >
      <div className="row wrap">
        <div className="field grow">
          <label htmlFor="media-search" className="sr-only">Search media</label>
          <input id="media-search" type="search" placeholder="Search by alt text or caption…" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <input ref={fileInput} type="file" accept="image/*" multiple hidden onChange={(e) => { upload(e.target.files); e.target.value = ""; }} />
        <button type="button" className="btn" disabled={busy} onClick={() => fileInput.current?.click()}>
          {busy ? "Uploading…" : "Upload images"}
        </button>
      </div>
      <p className="muted small">Drag and drop images anywhere on this panel to upload several at once.</p>

      {uploads.length > 0 && (
        <ul className="upload-list" aria-live="polite">
          {uploads.map((u) => (
            <li key={u.id} className={u.status}>
              <span className="grow">{u.name}</span>
              {u.status === "uploading" && <span>Uploading…</span>}
              {u.status === "done" && <span>Uploaded ✓</span>}
              {u.status === "error" && <span role="alert">✕ {u.error}</span>}
            </li>
          ))}
        </ul>
      )}

      {isLoading && <p className="muted">Loading media…</p>}
      {isError && (
        <div className="notice error" role="alert">
          {error.friendly} <button type="button" className="btn secondary small" onClick={() => refetch()}>Retry</button>
        </div>
      )}
      {!isLoading && !isError && items.length === 0 && (
        <div className="empty">{q ? "No images match your search." : "No images yet. Upload your first one."}</div>
      )}

      <ul className="media-grid">
        {items.map((asset) => (
          <li key={asset.id}>
            <button
              type="button"
              className={`media-thumb${asset.id === selectedId ? " selected" : ""}`}
              aria-pressed={asset.id === selectedId}
              onClick={() => onSelect?.(asset)}
              title={asset.caption || asset.alt_text || `Image ${asset.id}`}
            >
              <img src={asset.url} alt={asset.alt_text || ""} loading="lazy" />
              {!asset.alt_text && <span className="thumb-flag">No alt text</span>}
            </button>
          </li>
        ))}
      </ul>
      <Pagination pagination={data?.pagination} onPage={setPage} />
    </div>
  );
}
