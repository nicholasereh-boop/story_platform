import { useMutation, useQuery } from "@tanstack/react-query";
import { Link, useLocation } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { getAcademyConfig } from "../api/academy";
import { startCourseCheckout } from "../api/paid";
import { money } from "./formHelpers";
import { redirectTo } from "./redirect";

// The box on a PAID course page: buy, or continue when you already own it. The price shown is the course's own; the server
// decides the real amount and only unlocks the lessons after Paystack confirms the payment.
export default function PurchasePanel({ course, viewer, firstLessonId }) {
  const { user } = useAuth() || {};
  const location = useLocation();
  const config = useQuery({ queryKey: ["ac-config"], queryFn: getAcademyConfig, staleTime: 5 * 60 * 1000 });
  const pay = useMutation({ mutationFn: () => startCourseCheckout(course.id), onSuccess: (r) => redirectTo(r.authorization_url) });

  if (viewer.entitled) {
    const target = viewer.next_lesson_id || firstLessonId;
    return (
      <div className="ac-buy">
        <p className="ac-buy-title">You own this course ✓</p>
        {target ? <Link className="ac-btn ac-btn-primary" to={`/academy/learn/${target}`}>{viewer.completed > 0 ? "Continue learning" : "Start learning"}</Link> : null}
      </div>
    );
  }
  const paymentsOff = config.data && config.data.payments_enabled === false;
  return (
    <div className="ac-buy">
      <p className="ac-buy-price">{money(course.price, course.currency)}</p>
      <p className="ac-muted">One payment. Every lesson, yours to keep.</p>
      {!user ? (
        <Link className="ac-btn ac-btn-primary" to="/login" state={{ from: location.pathname, message: "Log in to buy this course." }}>Log in to buy</Link>
      ) : (
        <button type="button" className="ac-btn ac-btn-primary" disabled={pay.isPending || paymentsOff} onClick={() => pay.mutate()}>
          {pay.isPending ? "Opening checkout…" : `Buy for ${money(course.price, course.currency)}`}
        </button>
      )}
      {paymentsOff && <p className="ac-error" role="alert">Payments are not available right now.</p>}
      {pay.isError && <p className="ac-error" role="alert">{pay.error?.friendly || "Could not start the payment. Please try again."}</p>}
      <p className="ac-hint">🔒 Secure checkout with Paystack. You are charged the equivalent amount in naira at the current rate; your bank converts it to your own currency.</p>
    </div>
  );
}