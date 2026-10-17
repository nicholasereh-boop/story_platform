import { Link } from "react-router-dom";
import AnalyticsToggle from "../../components/public/AnalyticsToggle";
import { SITE_NAME } from "../../config";
import { usePublicMeta } from "../../hooks/usePublicMeta";

// Plain-language privacy notice for the visitor counting described in docs/ANALYTICS.md.
// Keep this page and the backend rules in step (retention default: 90 days).
export default function PrivacyPage() {
  usePublicMeta({ title: "Privacy", description: `How ${SITE_NAME} counts visitors, and how to opt out.`, path: "/privacy" });
  return (
    <div className="container narrow prose-page">
      <h1>Privacy</h1>
      <p>
        {SITE_NAME} counts visits so the team can see which stories people read. We do this ourselves: no advertising networks and no
        third-party analytics services. This page says exactly what is counted.
      </p>

      <h2>What we collect</h2>
      <ul>
        <li>A random code that your browser keeps in its local storage. We store only a scrambled (hashed) version of it, so it cannot be turned back into the original or linked to other sites.</li>
        <li>Which public page you opened (for example a story) and when.</li>
        <li>The website you came from, as a domain name only (for example “example.com”), and whether your device looks like a desktop, a phone or a tablet.</li>
      </ul>

      <h2>What we do not collect</h2>
      <ul>
        <li>Your IP address or your browser’s full identification text. They are never saved.</li>
        <li>Your name or email address. Visit counting is separate from accounts.</li>
        <li>Anything from the admin area, the log-in, sign-up and password pages or your account page.</li>
        <li>Visits from robots, and visits where your browser sends “Do Not Track” or “Global Privacy Control”.</li>
      </ul>
      <p>We do not use cookies for counting visits.</p>

      <h2>How long we keep it</h2>
      <p>
        Individual page views are deleted after 90 days (this is the default; the site owner can set a different time, never shorter
        than 35 days). Only totals, such as “120 visitors on Tuesday”, are kept after that. Browser codes not seen for about 13 months are deleted.
      </p>

      <h2>Opt out</h2>
      <p>
        Switch counting off here, or in the footer of any page. This is remembered in your browser. Turning on Do Not Track or Global
        Privacy Control in your browser also stops it.
      </p>
      <p><AnalyticsToggle /></p>
      <p className="muted small"><Link to="/">Back to the home page</Link></p>
    </div>
  );
}
