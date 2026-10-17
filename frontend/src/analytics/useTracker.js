import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { isExcludedPath, sendPageView, trackingAllowed } from "./tracker";

// Sends ONE page view per route change on the public site (single-page navigation counts too).
// It waits until the login state is known, so logged-in staff are never counted by accident.
export function useTracker() {
  const { pathname } = useLocation();
  const { ready, isStaff } = useAuth() || {};
  const lastPath = useRef(null); // guards against double sends (React StrictMode, auth state changing)
  const firstView = useRef(true);

  useEffect(() => {
    if (!ready || lastPath.current === pathname) return;
    lastPath.current = pathname;
    // Only the first page of a visit has an outside referrer; later pages were reached from our own site.
    const referrer = firstView.current && typeof document !== "undefined" ? document.referrer : "";
    firstView.current = false;
    if (isStaff || isExcludedPath(pathname) || !trackingAllowed()) return;
    sendPageView({ pathname, referrer });
  }, [pathname, ready, isStaff]);
}
