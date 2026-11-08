export default function ProviderBadge({ label, available }) {
  return (
    <span className={`vt-provider ${available ? "ok" : "closed"}`}>
      {label}
      <span className="vt-small" style={{ color: "inherit" }}>{available ? "· downloads available" : "· link check only"}</span>
    </span>
  );
}
