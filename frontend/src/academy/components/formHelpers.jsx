// Small shared pieces for the Academy forms.
export function firstError(err, ...fields) {
  for (const f of fields) {
    const v = err?.fieldErrors?.[f];
    const text = Array.isArray(v) ? v[0] : v;
    if (typeof text === "string" && text) return text;
  }
  const any = Object.values(err?.fieldErrors || {}).flat().find((x) => typeof x === "string");
  return any || err?.friendly || "Something went wrong. Please try again.";
}

export function Field({ id, label, error, hint, children }) {
  return (
    <div className={`ac-field${error ? " has-error" : ""}`}>
      <label htmlFor={id}>{label}</label>
      {children}
      {hint ? <p className="ac-hint">{hint}</p> : null}
      {error ? <p className="ac-error" role="alert">{error}</p> : null}
    </div>
  );
}

export function StatusChip({ status }) {
  const label = { draft: "Draft", published: "Published", archived: "Archived" }[status] || status;
  return <span className={`ac-status ac-status-${status}`}>{label}</span>;
}

export const money = (price, currency) => {
  const n = Number(price);
  if (!Number.isFinite(n) || n <= 0) return "Free";
  try {
    return new Intl.NumberFormat(currency === "NGN" ? "en-NG" : "en-US", { style: "currency", currency }).format(n);
  } catch {
    return `${n.toFixed(2)} ${currency}`;
  }
};