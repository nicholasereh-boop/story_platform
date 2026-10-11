import { useState } from "react";
import Modal from "../components/Modal";
import { extractYoutubeId } from "../utils/youtube";

// Insert a YouTube video from a URL or an 11-character id. Anything else shows an inline error.
export default function YoutubeDialog({ onInsert, onClose }) {
  const [value, setValue] = useState("");
  const [error, setError] = useState("");

  const submit = (event) => {
    event.preventDefault();
    const id = extractYoutubeId(value);
    if (!id) {
      setError("That is not a YouTube link. Use a youtube.com or youtu.be address starting with https://, or the 11-character video id.");
      return;
    }
    onInsert(id);
    onClose();
  };

  return (
    <Modal title="Insert YouTube video" onClose={onClose}>
      <form onSubmit={submit} noValidate>
        <div className="field">
          <label htmlFor="yt-url">YouTube link or video id</label>
          <input id="yt-url" data-autofocus value={value} onChange={(e) => { setValue(e.target.value); setError(""); }} placeholder="https://www.youtube.com/watch?v=…" aria-invalid={Boolean(error)} aria-describedby={error ? "yt-error" : undefined} />
          {error && <p id="yt-error" className="field-error" role="alert">{error}</p>}
        </div>
        <div className="row end">
          <button type="button" className="btn secondary" onClick={onClose}>Cancel</button>
          <button className="btn">Insert video</button>
        </div>
      </form>
    </Modal>
  );
}
