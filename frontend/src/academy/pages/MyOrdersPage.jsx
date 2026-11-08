import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import Pagination from "../../components/Pagination";
import { fmtDate } from "../../utils/format";
import { useDocumentMeta } from "../../hooks/useDocumentMeta";
import { getMyOrders, verifyCoursePayment } from "../api/paid";
import { money } from "../components/formHelpers";
import "../academy-paid.css";

const STATUS = { pending: "Pending", success: "Paid", failed: "Failed", refunded: "Refunded" };
const RETRY_MS = 4000;
const MAX_TRIES = 6;

// Where Paystack sends the learner back (?reference=...). The SERVER asks Paystack about the payment; this page only shows the answer.
function PaymentResult({ reference }) {
  const qc = useQueryClient();
  const [tries, setTries] = useState(0);
  const verify = useMutation({
    mutationFn: () => verifyCoursePayment(reference),
    onSuccess: (order) => {
      if (order.status === "success") { qc.invalidateQueries({ queryKey: ["ac-course"] }); qc.invalidateQueries({ queryKey: ["ac-my-learning"] }); qc.invalidateQueries({ queryKey: ["ac-orders"] }); }
    },
  });
  const started = useRef(false);
  useEffect(() => { if (!started.current) { started.current = true; verify.mutate(); } }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // A payment can take a moment to be confirmed: ask again a few times before giving up.
  const order = verify.data;
  useEffect(() => {
    if (order?.status === "pending" && tries < MAX_TRIES) {
      const id = setTimeout(() => { setTries((n) => n + 1); verify.mutate(); }, RETRY_MS);
      return () => clearTimeout(id);
    }
    return undefined;
  }, [order, tries]); // eslint-disable-line react-hooks/exhaustive-deps

  if (verify.isError) return <p className="ac-callout" role="alert">We could not check your payment just now. <button type="button" className="ac-link-btn" onClick={() => verify.mutate()}>Try again</button> — you have not been charged twice.</p>;
  if (!order) return <p className="ac-callout" role="status">Checking your payment…</p>;
  if (order.status === "success") {
    return (
      <div className="ac-callout ac-callout-ok" role="status">
        <strong>Payment confirmed 🎉</strong> You now own “{order.course.title}”.{" "}
        <Link className="ac-btn ac-btn-primary" to={`/academy/paid/courses/${order.course.slug}`}>Start learning</Link>
      </div>
    );
  }
  if (order.status === "pending") return <p className="ac-callout" role="status">Your payment is still being confirmed. This page will check again{tries >= MAX_TRIES ? ". If you were charged, your access appears as soon as it is confirmed: refresh this page in a few minutes." : "…"}</p>;
  if (order.status === "refunded") return <p className="ac-callout" role="status">This order was refunded.</p>;
  return <p className="ac-error" role="alert">The payment did not go through, so this order was not charged. You can try again from the course page.</p>;
}

export default function MyOrdersPage() {
  useDocumentMeta({ title: "My orders", robots: "noindex" });
  const [params] = useSearchParams();
  const reference = params.get("reference");
  const [page, setPage] = useState(1);
  const orders = useQuery({ queryKey: ["ac-orders", page], queryFn: () => getMyOrders({ page }), placeholderData: (previous) => previous });
  const items = orders.data?.items || [];
  return (
    <div className="ac-container">
      <header className="ac-page-head"><div><h1 className="ac-h1">My orders</h1><p className="ac-lede">Your course purchases.</p></div></header>
      {reference && <PaymentResult reference={reference} />}
      {orders.isLoading && <p className="ac-muted">Loading…</p>}
      {orders.data && items.length === 0 && <p className="ac-empty">No orders yet. <Link to="/academy/paid">Browse the premium courses</Link>.</p>}
      {items.length > 0 && (
        <div className="ac-table-wrap">
          <table className="ac-table">
            <thead><tr><th>Date</th><th>Course</th><th>Price</th><th>Charged</th><th>Status</th></tr></thead>
            <tbody>
              {items.map((o) => (
                <tr key={o.id}>
                  <td>{fmtDate(o.created_at)}</td>
                  <td><Link to={`/academy/paid/courses/${o.course.slug}`}>{o.course.title}</Link></td>
                  <td>{money(o.list_price ?? o.amount, o.list_currency || o.currency)}</td>
                  <td>{o.list_currency && o.list_currency !== o.currency ? money(o.amount, o.currency) : "Same"}</td>
                  <td><span className={`ac-status ac-status-${o.status === "success" ? "published" : o.status === "pending" ? "draft" : "archived"}`}>{STATUS[o.status] || o.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {orders.data && <Pagination pagination={orders.data.pagination} onPage={(n) => { setPage(n); window.scrollTo?.(0, 0); }} />}
    </div>
  );
}