import { useState } from "react";
import { browserSaysNo, isOptedOut, setOptedOut } from "../../analytics/tracker";

// "Analytics: on / off" in the footer. A notice plus an opt-out, not a consent banner (see /privacy).
export default function AnalyticsToggle() {
  const [off, setOff] = useState(() => isOptedOut());
  const browser = browserSaysNo();

  if (browser) {
    return <span className="analytics-toggle muted">Analytics: off (your browser asks not to be tracked)</span>;
  }
  const flip = () => {
    const next = !off;
    setOptedOut(next); // if the browser cannot store it, the choice still holds until the page is closed
    setOff(next);
  };
  return (
    <button type="button" className="link-button analytics-toggle" aria-pressed={!off} onClick={flip}>
      Analytics: {off ? "off" : "on"}
    </button>
  );
}
