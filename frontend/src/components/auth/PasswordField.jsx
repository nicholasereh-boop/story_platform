import { useId, useState } from "react";

// Label + password input + accessible show/hide control + field error/hint.
export default function PasswordField({ label, value, onChange, error, autoComplete, hint, id }) {
  const auto = useId();
  const fieldId = id || auto;
  const [visible, setVisible] = useState(false);
  const describedBy = error ? `${fieldId}-error` : hint ? `${fieldId}-hint` : undefined;

  return (
    <div className="field">
      <label htmlFor={fieldId}>{label}</label>
      <div className="password-input-wrap">
        <input
          id={fieldId}
          type={visible ? "text" : "password"}
          autoComplete={autoComplete}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          aria-invalid={error ? "true" : undefined}
          aria-describedby={describedBy}
        />
        <button
          className="password-toggle"
          type="button"
          onClick={() => setVisible((shown) => !shown)}
          aria-controls={fieldId}
          aria-label={visible ? "Hide password" : "Show password"}
          aria-pressed={visible}
        >
          {visible ? "Hide" : "Show"}
        </button>
      </div>
      {error ? <p className="field-error" id={`${fieldId}-error`}>{error}</p> : hint ? <p className="hint" id={`${fieldId}-hint`}>{hint}</p> : null}
    </div>
  );
}
