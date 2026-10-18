import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { configureTracker, isExcludedPath, sendPageView, trackingAllowed } from "./tracker";

// Sends ONE page view per route change on the public site (single-page navigation counts too).
// It waits until the login state is known, so logged-in staff are never counted by accident, and until the site's
// consent mode is known (`configReady`), so nobody is counted before we know the rules. `version` changes whenever the
// visitor makes a consent choice: if that makes counting allowed, the page they are on is counted once.
export function useTracker({ configReady = true, mode = "notice", enabled = true, version = 0 } = {}) {
  const { pathname } = useLocation();
  const { ready, isStaff } = useAuth() || {};
  const lastPath = useRef(null); // the path already counted: guards against double sends (React StrictMode, state changes)
  const firstView = useRef(true);

  useEffect(() => {
    if (!ready || !configReady) return;
    configureTracker({ mode, enabled });
    // Only the first page of a visit has an outside referrer; later pages were reached from our own site.
    const referrer = firstView.current && typeof document !== "undefined" ? document.referrer : "";
    firstView.current = false;
    if (isStaff || isExcludedPath(pathname) || !trackingAllowed()) return;
    if (lastPath.current === pathname) return;
    lastPath.current = pathname;
    sendPageView({ pathname, referrer });
  }, [pathname, ready, isStaff, configReady, mode, enabled, version]);
}
