import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getPrivacyPolicy } from "../../api/security";
import AnalyticsToggle from "../../components/public/AnalyticsToggle";
import { SITE_NAME } from "../../config";
import { usePublicMeta } from "../../hooks/usePublicMeta";
import { useConsent } from "../../privacy/ConsentContext";
import { STORAGE_KEYS } from "../../privacy/storageKeys";

const days = (n) => `${n} day${n === 1 ? "" : "s"}`;

function Table({ caption, head, rows }) {
  return (
    <div className="table-wrap">
      <table className="policy-table">
        <caption>{caption}</caption>
        <thead>
          <tr>{head.map((h) => <th key={h} scope="col">{h}</th>)}</tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
  );
}

// The privacy policy. Every NUMBER and NAME on this page comes from the server's live settings
// (/api/v1/privacy-policy/), so it cannot promise something the server does not do. The legal wording is generic and
// needs review by the site owner (marked on the page).
export default function PrivacyPage() {
  usePublicMeta({ title: "Privacy policy", description: `What ${SITE_NAME} collects, why, for how long, and your rights.`, path: "/privacy" });
  const consent = useConsent();
  const policy = useQuery({ queryKey: ["privacy-policy"], queryFn: getPrivacyPolicy, staleTime: 5 * 60_000, retry: 1 });

  if (policy.isLoading) return <div className="container narrow"><p className="muted">Loading the privacy policy…</p></div>;
  if (policy.isError) {
    return (
      <div className="container narrow" role="alert">
        <h1>Privacy policy</h1>
        <p>The privacy policy could not be loaded: {policy.error.friendly} Please try again in a moment.</p>
        <button type="button" className="btn secondary" onClick={() => policy.refetch()}>Try again</button>
      </div>
    );
  }

  const p = policy.data;
  const site = p.site_name || SITE_NAME;
  const operator = p.operator_name || site;
  const r = p.retention;
  const contact = p.contact_email ? <a href={`mailto:${p.contact_email}`}>{p.contact_email}</a> : <em>(the site owner has not published a contact address yet)</em>;

  return (
    <div className="container narrow prose-page">
      <h1>Privacy policy</h1>
      <p className="muted small">Effective date: {p.effective_date || "not yet set by the site owner"}</p>
      <div className="notice info" role="note">
        <strong>Note for the site owner:</strong> the legal wording on this page is general. It must be reviewed and confirmed for
        your country before the site goes live. Numbers and tables below are read from the server&apos;s real settings.
      </div>

      <h2>Who is responsible</h2>
      <p>{operator} runs {site}. Questions about your data: {contact}.</p>

      <h2>What we collect, and why</h2>
      <ul>
        <li><strong>Account</strong> (only if you sign up): your email address, a password (stored only as a one-way hash) or your Google sign-in, your display name and optional short bio. Why: to let you log in, like stories and comment.</li>
        <li><strong>Comments and likes</strong>: what you write and which stories you like. Comments are public under your display name once approved. Likes are not shown to other people by name.</li>
        {p.analytics_enabled ? (
          <li><strong>Visit counting</strong>: a random code kept in your browser (we store only a hashed copy), the public page you opened, the website you came from (domain only), and whether you use a desktop, phone or tablet. We never save your IP address or your browser&apos;s full identification text, and nothing is counted in the admin, log-in, sign-up or account pages. Why: to see which stories people read.</li>
        ) : (
          <li><strong>Visit counting</strong> is switched off on this site.</li>
        )}
        <li><strong>Security records</strong>: staff actions are written to an audit log (who did what, when) and sessions are listed so you can sign out of other devices. The audit log keeps a scrambled form of the IP address, never the address itself.</li>
        <li><strong>Technical logs</strong>: server logs with passwords, tokens and email addresses removed.</li>
      </ul>

      <h2>Legal basis</h2>
      <p className="muted"><em>To be confirmed by the site owner.</em> In general terms: account, comments and likes are processed to provide the service you asked for; visit counting and security records serve the site&apos;s legitimate interest in understanding and protecting the service{p.consent_mode === "opt_in" ? "; visit counting only starts if you accept in the privacy banner" : ""}.</p>

      <h2>How long we keep it</h2>
      <ul>
        <li>Individual page views: {days(r.analytics_events_days)}. After that only totals (for example &ldquo;120 visitors on Tuesday&rdquo;) are kept.</li>
        <li>Browser codes not seen for {days(r.analytics_visitors_days)} are deleted.</li>
        <li>Audit log entries: {days(r.audit_log_days)}.</li>
        <li>Comments and likes: until you delete your account or a moderator removes them. You can edit a comment for {r.comment_edit_window_minutes} minutes after posting.</li>
        <li>Deleted accounts: erased at once. Your email address, name, bio, picture and sign-in methods are removed, your likes are deleted and your comments are removed from the site; what remains is an empty, deactivated account record that no longer points to you.</li>
      </ul>

      <h2>Who can see what</h2>
      <ul>
        <li>Everyone: stories, approved comments with display names.</li>
        <li>You: your own account, comments, likes and sessions.</li>
        <li>Staff: account list (email, display name, role, status), comments for moderation, visit totals and the audit log. Staff cannot see your password or your visit-counting code.</li>
        <li>Service providers: the hosting, email and (if you use it) Google sign-in providers handle data on our behalf as needed to run the site.</li>
      </ul>

      <h2>Your rights</h2>
      <p>
        You can <Link to="/account">download your data</Link> and <Link to="/account">delete your account</Link> yourself from your
        account page. You can also ask us to correct or remove data, or object to processing, by writing to {contact}. Depending on where
        you live you may also have the right to complain to your data-protection authority.
      </p>

      <h2>Cookies and browser storage</h2>
      <p>We set only the cookies that are strictly necessary to run the site. Nothing else sets a cookie: no advertising, no third-party analytics.</p>
      <Table
        caption="Cookies"
        head={["Name", "Purpose", "Lasts", "Strictly necessary"]}
        rows={p.cookies.map((c) => (
          <tr key={c.name}>
            <td><code>{c.name}</code></td><td>{c.purpose}</td><td>{c.duration}</td><td>{c.necessary ? "Yes" : "No"}</td>
          </tr>
        ))}
      />
      <Table
        caption="Browser storage (localStorage and sessionStorage)"
        head={["Key", "Where", "Purpose", "Lasts", "Strictly necessary"]}
        rows={STORAGE_KEYS.map((k) => (
          <tr key={k.key}>
            <td><code>{k.key}</code></td><td>{k.storage}</td><td>{k.purpose}</td><td>{k.duration}</td><td>{k.necessary ? "Yes" : "No"}</td>
          </tr>
        ))}
      />

      {p.analytics_enabled && (
        <>
          <h2>Your choice about visit counting</h2>
          {p.consent_mode === "notice" && (
            <>
              <p>Counting is on unless you switch it off here or in the footer. It also stays off when your browser sends &ldquo;Do Not Track&rdquo; or &ldquo;Global Privacy Control&rdquo;.</p>
              <p><AnalyticsToggle /></p>
            </>
          )}
          {p.consent_mode !== "notice" && (
            <>
              <p>
                {p.consent_mode === "opt_in" ? "Counting stays off until you accept." : "Counting is on until you reject."} Your answer is kept only in this browser for 6 months.
                It also stays off when your browser sends &ldquo;Do Not Track&rdquo; or &ldquo;Global Privacy Control&rdquo;.
              </p>
              <p><button type="button" className="btn secondary" onClick={consent.reopen}>Change my privacy choice</button></p>
            </>
          )}
        </>
      )}
      <p className="muted small"><Link to="/">Back to the home page</Link></p>
    </div>
  );
}
