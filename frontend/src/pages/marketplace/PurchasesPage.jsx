import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { downloadPackage, myPurchases, verifyPayment } from "../../api/marketplace";
import Pagination from "../../components/Pagination";
import QueryState from "../../components/public/QueryState";
import { ProjectStatus, KIND_LABELS } from "../../components/marketplace/shared";
import { useDocumentMeta } from "../../hooks/useDocumentMeta";
import { formatPrice } from "../../utils/money";
import { saveBlob } from "../../utils/saveBlob";
import "./marketplace.css";

// Paystack sends the buyer back here with ?reference=…. We never trust that: the SERVER asks Paystack and tells us
// whether the payment really went through; only then does "Download" appear.
function PaymentResult({ reference, onDone }) {
  const started = useRef(false);
  const verify = useMutation({ mutationFn: () => verifyPayment(reference), onSettled: onDone });
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    verify.mutate();
  }, [verify]);

  if (verify.isPending || verify.isIdle) return <p className="notice" role="status">Confirming your payment…</p>;
  if (verify.isError) return <p className="notice error" role="alert">{verify.error.friendly} Your purchase will appear below once the payment is confirmed. <button type="button" className="link-button" onClick={() => verify.mutate()}>Check again</button></p>;
  const status = verify.data.status;
  if (status === "success") return <p className="notice" role="status">Payment confirmed. You can download your package below.</p>;
  if (status === "failed") return <p className="notice error" role="alert">The payment did not go through, so nothing was charged to this order. You can try again from the project page.</p>;
  return <p className="notice" role="status">Your payment is still being processed. <button type="button" className="link-button" onClick={() => verify.mutate()}>Check again</button></p>;
}

export default function PurchasesPage() {
  useDocumentMeta({ title: "My purchases", robots: "noindex" });
  const [params, setParams] = useSearchParams();
  // Captured once: the address is cleaned up after verifying, but the result message must stay on screen.
  const [reference] = useState(() => params.get("reference"));
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(null);
  const query = useQuery({ queryKey: ["mp-purchases", page], queryFn: () => myPurchases({ page }), placeholderData: (p) => p });

  async function download(p) {
    setBusy(p.id);
    setError("");
    try {
      const { blob, filename } = await downloadPackage(p.package_id, `${p.project.slug}-${p.kind}.zip`);
      saveBlob(blob, filename);
    } catch (err) {
      setError(err.friendly || "The download failed.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="container">
      <div className="mp-head"><h1>My purchases</h1><Link className="btn secondary" to="/marketplace">Browse the marketplace</Link></div>
      {reference && <PaymentResult reference={reference} onDone={() => { qc.invalidateQueries({ queryKey: ["mp-purchases"] }); setParams({}, { replace: true }); }} />}
      {error && <p className="field-error" role="alert">{error}</p>}
      <QueryState query={query} skeleton={<p className="muted">Loading…</p>} isEmpty={(d) => d.items.length === 0}
        empty={<div className="empty"><p>No purchases yet.</p></div>}>
        {(data) => (
          <>
            <div className="table-wrap">
              <table className="table">
                <caption className="sr-only">Your purchases</caption>
                <thead><tr><th scope="col">Project</th><th scope="col">Package</th><th scope="col">Price</th><th scope="col">Status</th><th scope="col"><span className="sr-only">Download</span></th></tr></thead>
                <tbody>
                  {data.items.map((p) => (
                    <tr key={p.id}>
                      <th scope="row"><Link to={`/marketplace/projects/${p.project.slug}`}>{p.project.title}</Link></th>
                      <td>{KIND_LABELS[p.kind]} v{p.version}</td>
                      <td>{p.list_price && p.list_currency !== p.currency ? `${formatPrice(p.list_price, p.list_currency)} (charged ${formatPrice(p.amount, p.currency)})` : formatPrice(p.amount, p.currency)}</td>
                      <td><ProjectStatus status={p.status} /></td>
                      <td>{p.can_download && <button type="button" className="btn small" disabled={busy === p.id} onClick={() => download(p)}>{busy === p.id ? "Preparing…" : "Download"}</button>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination pagination={data.pagination} onPage={setPage} />
          </>
        )}
      </QueryState>
    </div>
  );
}
