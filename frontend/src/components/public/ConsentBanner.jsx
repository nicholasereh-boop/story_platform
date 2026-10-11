import { Link, useLocation } from "react-router-dom";
import { isExcludedPath } from "../../analytics/tracker";
import { useConsent } from "../../privacy/ConsentContext";

// The privacy banner (only for consent modes "opt_in" and "opt_out"). Accept and Reject are the same size and style on
// purpose. It is a region at the bottom of the page, NOT a modal: it never traps focus or blocks reading. It is never
// shown on the admin, log-in, sign-up or account pages (nothing is counted there anyway).
export default function ConsentBanner() {
  const { mode, bannerOpen, accept, reject } = useConsent();
  const { pathname } = useLocation();
  if (!bannerOpen || isExcludedPath(pathname)) return null;
  return (
    <section className="consent-banner" aria-labelledby="consent-title">
      <h2 id="consent-title">Your privacy choice</h2>
      <p>
        {mode === "opt_in"
          ? "We would like to count visits to see which stories are read. Nothing is counted unless you accept."
          : "We count visits to see which stories are read. Counting is on unless you reject it."}{" "}
        No cookies, no advertising, no third parties. <Link to="/privacy">Read the privacy policy</Link>.
      </p>
      <div className="consent-actions">
        <button type="button" className="btn" onClick={accept}>Accept</button>
        <button type="button" className="btn" onClick={reject}>Reject</button>
      </div>
    </section>
  );
}
