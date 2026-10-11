import { useId } from "react";

// Label + text/email input + error, wired for screen readers.
export default function TextField({ label, value, onChange, error, type = "text", autoComplete, hint, id, ...rest }) {
  const auto = useId();
  const fieldId = id || auto;
  const describedBy = error ? `${fieldId}-error` : hint ? `${fieldId}-hint` : undefined;
  return (
    <div className="field">
      <label htmlFor={fieldId}>{label}</label>
      <input
        id={fieldId}
        type={type}
        autoComplete={autoComplete}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-invalid={error ? "true" : undefined}
        aria-describedby={describedBy}
        {...rest}
      />
      {error ? <p className="field-error" id={`${fieldId}-error`}>{error}</p> : hint ? <p className="hint" id={`${fieldId}-hint`}>{hint}</p> : null}
    </div>
  );
}
