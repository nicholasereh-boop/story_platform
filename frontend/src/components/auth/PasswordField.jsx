import { useId } from "react";

// Label + password input + (client or server) error, wired for screen readers.
export default function PasswordField({ label, value, onChange, error, autoComplete, hint, id }) {
  const auto = useId();
  const fieldId = id || auto;
  const describedBy = error ? `${fieldId}-error` : hint ? `${fieldId}-hint` : undefined;
  return (
    <div className="field">
      <label htmlFor={fieldId}>{label}</label>
      <input
        id={fieldId}
        type="password"
        autoComplete={autoComplete}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-invalid={error ? "true" : undefined}
        aria-describedby={describedBy}
      />
      {error ? <p className="field-error" id={`${fieldId}-error`}>{error}</p> : hint ? <p className="hint" id={`${fieldId}-hint`}>{hint}</p> : null}
    </div>
  );
}
