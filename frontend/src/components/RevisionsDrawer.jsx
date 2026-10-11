import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { listRevisions, restoreRevision } from "../api";
import { fmtDateTime } from "../utils/format";
import ConfirmDialog from "./ConfirmDialog";
import Modal from "./Modal";
import Pagination from "./Pagination";
import StoryRenderer from "./StoryRenderer";

// Right-hand drawer: list of saved versions, read-only preview, and "Restore this version".
export default function RevisionsDrawer({ storyId, hasUnsaved, onRestored, onClose }) {
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState(null);
  const [confirming, setConfirming] = useState(false);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["revisions", storyId, page],
    queryFn: () => listRevisions(storyId, { page }),
    gcTime: 0,
  });

  const restore = useMutation({
    mutationFn: () => restoreRevision(storyId, selected.id),
    onSuccess: () => { setConfirming(false); onRestored(); onClose(); },
  });

  const items = data?.items || [];

  return (
    <Modal title="Revision history" onClose={onClose} drawer>
      {isLoading && <p className="muted">Loading revisions…</p>}
      {isError && <div className="notice error" role="alert">{error.friendly}</div>}
      {!isLoading && !isError && items.length === 0 && <div className="empty">No saved versions yet.</div>}

      <ul className="rev-list">
        {items.map((rev) => (
          <li key={rev.id}>
            <button type="button" className={selected?.id === rev.id ? "on" : undefined} aria-pressed={selected?.id === rev.id} onClick={() => setSelected(rev)}>
              <strong>Version {rev.revision_number}</strong>
              <span className="muted small"> {rev.author || "Unknown"} · {fmtDateTime(rev.created_at)}</span>
            </button>
          </li>
        ))}
      </ul>
      <Pagination pagination={data?.pagination} onPage={setPage} />

      {selected && (
        <section className="rev-preview" aria-label={`Preview of version ${selected.revision_number}`}>
          <h3>{selected.title || "(Untitled)"}</h3>
          <StoryRenderer content={selected.content_json} />
          {restore.isError && <div className="notice error" role="alert">{restore.error.friendly}</div>}
          <div className="row end sticky-foot">
            <button type="button" className="btn" onClick={() => setConfirming(true)}>Restore this version</button>
          </div>
        </section>
      )}

      {confirming && (
        <ConfirmDialog
          title="Restore this version?"
          message={`The editor will go back to version ${selected.revision_number}.${hasUnsaved ? " Your unsaved changes will be replaced." : ""} The current version stays in the history.`}
          confirmLabel="Restore"
          busy={restore.isPending}
          onCancel={() => setConfirming(false)}
          onConfirm={() => restore.mutate()}
        />
      )}
    </Modal>
  );
}
