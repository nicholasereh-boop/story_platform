// "49" + "USD" -> "$49.00", "5000.50" + "NGN" -> "₦5,000.50". Free packages say "Free".
// Falls back to "49.00 XYZ" if the currency code is unknown.
export function formatPrice(amount, currency = "USD") {
  const n = Number(amount);
  if (!Number.isFinite(n) || n <= 0) return "Free";
  try {
    return new Intl.NumberFormat(currency === "NGN" ? "en-NG" : "en-US", { style: "currency", currency }).format(n);
  } catch {
    return `${n.toFixed(2)} ${currency}`;
  }
}

export function formatBytes(bytes) {
  const n = Number(bytes) || 0;
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(1)} MB`;
  return `${(n / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}
