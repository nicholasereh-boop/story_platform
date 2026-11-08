import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { downloadPackage, startCheckout } from "../../api/marketplace";
import { formatBytes, formatPrice } from "../../utils/money";
import { saveBlob } from "../../utils/saveBlob";
import { KIND_LABELS } from "./shared";

// One box per package: price, what it is, and the right button for THIS reader.
//   free + signed in        -> Download
//   free + signed out       -> Log in to download
//   paid, already bought    -> Download
//   paid (backend code)     -> "Download ... $49.00": clicking it takes the reader to PAYSTACK first (in dollars), and the
//                              download unlocks only after the server has confirmed the payment
// The page only chooses a button; the server re-checks every download and every price.
export default function PackageActions({ project }) {
  const { user } = useAuth();
  const location = useLocation();
  const viewer = project.viewer?.packages || {};
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  if (project.offers.length === 0) return <p className="muted">No files have been added to this project yet.</p>;

  async function download(offer) {
    setBusy(offer.kind);
    setError("");
    try {
      const { blob, filename } = await downloadPackage(offer.package_id, `${project.slug}-${offer.kind}.zip`);
      saveBlob(blob, filename);
    } catch (err) {
      setError(err.friendly || "The download failed. Please try again.");
    } finally {
      setBusy("");
    }
  }

  async function buy(offer) {
    setBusy(offer.kind);
    setError("");
    try {
      const { authorization_url: url } = await startCheckout(project.id, offer.kind);
      if (typeof url === "string" && url.startsWith("https://")) {
        window.location.assign(url); // Paystack's secure payment page
        return;
      }
      setError("We could not start the payment. Please try again.");
    } catch (err) {
      setError(err.friendly || "We could not start the payment. Please try again.");
    }
    setBusy("");
  }

  const loginState = { from: `${location.pathname}${location.search}`, message: "Log in to get this project." };

  return (
    <div>
      {project.offers.map((offer) => {
        const mine = viewer[offer.kind] || {};
        const label = KIND_LABELS[offer.kind];
        return (
          <div className="mp-offer" key={offer.kind}>
            <h3>{label} package</h3>
            <p className="mp-offer-price">{formatPrice(offer.price, offer.currency)}</p>
            <p className="mp-meta">Version {offer.version} · {formatBytes(offer.size_bytes)} · {offer.file_count} {offer.file_count === 1 ? "file" : "files"}</p>
            {mine.can_download ? (
              <button type="button" className="btn" disabled={busy === offer.kind} onClick={() => download(offer)}>
                {busy === offer.kind ? "Preparing…" : mine.basis === "owner" ? `Download your ${label.toLowerCase()} package` : `Download ${label.toLowerCase()} package`}
              </button>
            ) : !user ? (
              <Link className="btn" to="/login" state={loginState}>{offer.is_free ? "Log in to download" : `Log in to download ${label.toLowerCase()} · ${formatPrice(offer.price, offer.currency)}`}</Link>
            ) : (
              <button type="button" className="btn" disabled={busy === offer.kind} onClick={() => buy(offer)}>
                {busy === offer.kind ? "Opening Paystack…" : `Download ${label.toLowerCase()} package · ${formatPrice(offer.price, offer.currency)}`}
              </button>
            )}
            {!mine.can_download && !offer.is_free && (
              <p className="mp-meta" role="note">
                Paid package. You will pay {formatPrice(offer.price, offer.currency)} securely with Paystack first, then the download unlocks. Paystack charges the equivalent amount in Nigerian naira at the current rate, and your bank converts it to your own currency.
              </p>
            )}
          </div>
        );
      })}
      {error ? <p className="field-error" role="alert">{error}</p> : null}
    </div>
  );
}
