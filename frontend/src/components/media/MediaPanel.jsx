import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { deleteMedia, getMedia, updateMedia } from "../../api";

export default function MediaPanel({ assetId, onClose }) {
  const queryClient = useQueryClient();
  const { data: asset, isLoading, isError, error } = useQuery({
    queryKey: ["media-detail", assetId],
    queryFn: () => getMedia(assetId),
  });
  const [message, setMessage] = useState("");
  const saveMutation = useMutation({
    mutationFn: (body) => updateMedia(assetId, body),
    onSuccess: (updated) => {
      queryClient.setQueryData(["media-detail", assetId], updated);
      queryClient.invalidateQueries({ queryKey: ["media"] });
      setMessage("Changes saved.");
    },
  });
  const deleteMutation = useMutation({
    mutationFn: () => deleteMedia(assetId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["media"] });
      onClose?.();
    },
  });

  if (isLoading) return <aside className="media-panel" aria-label="Media details"><p>Loading media details…</p></aside>;
  if (isError) return <aside className="media-panel" aria-label="Media details"><p role="alert">{error?.friendly || "Could not load media details."}</p><button type="button" className="btn secondary" onClick={onClose}>Close</button></aside>;
  if (!asset) return null;

  const save = (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    saveMutation.mutate({ alt_text: String(form.get("alt_text") || "").trim(), caption: String(form.get("caption") || "").trim() });
  };

  return (
    <aside className="media-panel" aria-label="Media details">
      <div className="row wrap">
        <h2 className="grow">Image details</h2>
        <button type="button" className="btn secondary small" onClick={onClose}>Close</button>
      </div>
      <img src={asset.url} alt={asset.alt_text || "Selected media"} className="media-detail-image" />
      <form onSubmit={save}>
        <div className="field">
          <label htmlFor="media-alt-text">Alt text</label>
          <input id="media-alt-text" name="alt_text" defaultValue={asset.alt_text || ""} maxLength={500} />
        </div>
        <div className="field">
          <label htmlFor="media-caption">Caption</label>
          <textarea id="media-caption" name="caption" defaultValue={asset.caption || ""} rows={3} maxLength={2000} />
        </div>
        {message && <p role="status" className="muted small">{message}</p>}
        {saveMutation.isError && <p role="alert" className="notice error">{saveMutation.error?.friendly || "Could not save changes."}</p>}
        <button type="submit" className="btn" disabled={saveMutation.isPending}>{saveMutation.isPending ? "Saving…" : "Save details"}</button>
      </form>
      {asset.used_in?.length > 0 && (
        <section aria-label="Image usage">
          <h3>Used in</h3>
          <ul>{asset.used_in.map((usage, index) => <li key={usage.id || index}>{usage.title || usage.name || "Story"}</li>)}</ul>
        </section>
      )}
      <button type="button" className="btn danger" disabled={deleteMutation.isPending} onClick={() => {
        if (window.confirm("Delete this image? This cannot be undone.")) deleteMutation.mutate();
      }}>{deleteMutation.isPending ? "Deleting…" : "Delete image"}</button>
      {deleteMutation.isError && <p role="alert" className="notice error">{deleteMutation.error?.friendly || "Could not delete this image."}</p>}
    </aside>
  );
}
