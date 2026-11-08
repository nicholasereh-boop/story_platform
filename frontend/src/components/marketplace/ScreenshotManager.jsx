import { useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { deleteScreenshot, uploadScreenshots } from "../../api/marketplace";
import { firstError, safeImageSrc } from "./shared";

export const MAX_SCREENSHOTS = 8;

export default function ScreenshotManager({ projectId, screenshots, onChanged }) {
  const ref = useRef(null);
  const [alt, setAlt] = useState("");
  const full = screenshots.length >= MAX_SCREENSHOTS;

  const add = useMutation({
    mutationFn: (files) => uploadScreenshots(projectId, files, alt.trim()),
    onSuccess: () => {
      if (ref.current) ref.current.value = "";
      setAlt("");
      onChanged();
    },
  });
  const remove = useMutation({ mutationFn: (id) => deleteScreenshot(projectId, id), onSuccess: onChanged });

  const submit = (e) => {
    e.preventDefault();
    const files = ref.current?.files;
    if (files && files.length) add.mutate(files);
  };

  return (
    <section className="mp-section" aria-labelledby="shots-h">
      <h2 id="shots-h">Screenshots</h2>
      {screenshots.length > 0 && (
        <ul className="mp-shots">
          {screenshots.map((s, i) => (
            <li key={s.id}>
              {safeImageSrc(s.url) && <img src={safeImageSrc(s.url)} alt={s.alt_text || `Screenshot ${i + 1}`} />}
              <button type="button" className="link-button" disabled={remove.isPending} onClick={() => remove.mutate(s.id)} aria-label={`Remove screenshot ${i + 1}`}>Remove</button>
            </li>
          ))}
        </ul>
      )}
      <form onSubmit={submit} className="stack">
        <div className="field">
          <label htmlFor="shot-file">Add screenshots (up to {MAX_SCREENSHOTS})</label>
          <input id="shot-file" ref={ref} type="file" accept="image/png,image/jpeg,image/webp,image/gif" multiple disabled={full || add.isPending} />
          <p className="hint">The first one is the cover image. Images are checked and re-saved on our side.</p>
        </div>
        <div className="field">
          <label htmlFor="shot-alt">Describe the image (for people using screen readers)</label>
          <input id="shot-alt" value={alt} onChange={(e) => setAlt(e.target.value)} maxLength={300} disabled={full || add.isPending} />
        </div>
        {add.isError && <p className="field-error" role="alert">{firstError(add.error, "file")}</p>}
        <button type="submit" className="btn small" disabled={full || add.isPending}>{add.isPending ? "Uploading…" : "Upload"}</button>
        {full && <p className="muted">You have reached the limit of {MAX_SCREENSHOTS} screenshots.</p>}
      </form>
    </section>
  );
}
