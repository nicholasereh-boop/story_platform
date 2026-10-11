import Modal from "./Modal";

// "Are you sure?" dialog. The safe button (Cancel) gets the initial focus.
export default function ConfirmDialog({ title, message, confirmLabel = "Confirm", danger = false, busy = false, onConfirm, onCancel, children }) {
  return (
    <Modal title={title} onClose={onCancel}>
      <p>{message}</p>
      {children}
      <div className="row end">
        <button type="button" className="btn secondary" data-autofocus onClick={onCancel}>Cancel</button>
        <button type="button" className={`btn${danger ? " danger" : ""}`} disabled={busy} onClick={onConfirm}>
          {busy ? "Working…" : confirmLabel}
        </button>
      </div>
    </Modal>
  );
}
