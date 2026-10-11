import { useEffect, useId, useRef } from "react";
import { createPortal } from "react-dom";

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

// Accessible modal: role=dialog, focus moves in and is TRAPPED (Tab cycles inside), Esc closes,
// focus returns to whatever opened it.
export default function Modal({ title, onClose, children, wide = false, drawer = false }) {
  const ref = useRef(null);
  const titleId = useId();

  useEffect(() => {
    const opener = document.activeElement;
    const root = ref.current;
    const first = root?.querySelector("[data-autofocus]") || root?.querySelector(FOCUSABLE);
    (first || root)?.focus();

    const onKey = (event) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        onClose();
        return;
      }
      if (event.key !== "Tab" || !root) return;
      const items = Array.from(root.querySelectorAll(FOCUSABLE));
      if (items.length === 0) {
        event.preventDefault();
        return;
      }
      const firstEl = items[0];
      const lastEl = items[items.length - 1];
      if (event.shiftKey && document.activeElement === firstEl) {
        event.preventDefault();
        lastEl.focus();
      } else if (!event.shiftKey && document.activeElement === lastEl) {
        event.preventDefault();
        firstEl.focus();
      } else if (!root.contains(document.activeElement)) {
        event.preventDefault();
        firstEl.focus();
      }
    };
    document.addEventListener("keydown", onKey, true);
    return () => {
      document.removeEventListener("keydown", onKey, true);
      if (opener && typeof opener.focus === "function") opener.focus();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return createPortal(
    <div className={`modal-backdrop${drawer ? " drawer-backdrop" : ""}`} onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div ref={ref} className={`modal${wide ? " wide" : ""}${drawer ? " drawer" : ""}`} role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1}>
        <div className="modal-head">
          <h2 id={titleId}>{title}</h2>
          <button type="button" className="btn ghost small" aria-label="Close dialog" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>,
    document.body
  );
}
