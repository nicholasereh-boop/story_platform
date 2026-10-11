import { useState } from "react";
import Modal from "../components/Modal";
import { normalizeLink } from "../utils/links";

// Add / edit / remove a link. The address is validated with the same rules as the server.
export default function LinkDialog({ initialHref = "", hasLink = false, onApply, onRemove, onClose }) {
  const [value, setValue] = useState(initialHref);
  const [error, setError] = useState("");

  const submit = (event) => {
    event.preventDefault();
    const href = normalizeLink(value);
    if (!href) {
      setError("Enter a web address (https://…) or an email address. Other kinds of links are not allowed.");
      return;
    }
    onApply(href);
    onClose();
  };

  return (
    <Modal title={hasLink ? "Edit link" : "Add link"} onClose={onClose}>
      <form onSubmit={submit} noValidate>
        <div className="field">
          <label htmlFor="link-url">Web address</label>
          <input id="link-url" data-autofocus value={value} onChange={(e) => { setValue(e.target.value); setError(""); }} placeholder="https://example.com" aria-invalid={Boolean(error)} aria-describedby={error ? "link-error" : undefined} />
          {error && <p id="link-error" className="field-error" role="alert">{error}</p>}
        </div>
        <div className="row end">
          {hasLink && <button type="button" className="btn danger" onClick={() => { onRemove(); onClose(); }}>Remove link</button>}
          <button type="button" className="btn secondary" onClick={onClose}>Cancel</button>
          <button className="btn">Apply</button>
        </div>
      </form>
    </Modal>
  );
}
