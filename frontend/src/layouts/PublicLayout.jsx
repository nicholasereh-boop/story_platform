import { useEffect, useRef } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { useTracker } from "../analytics/useTracker";
import Footer from "../components/public/Footer";
import Header from "../components/public/Header";
import ConsentBanner from "../components/public/ConsentBanner";
import { SignupPromptProvider } from "../engagement/SignupPromptContext";
import { ConsentProvider, useConsent } from "../privacy/ConsentContext";
import { usePublicConfig } from "../privacy/usePublicConfig";

// Frame of every public page: skip link, header, <main>, footer. Routes inside it fill <main>.
// SignupPromptProvider wraps it all so any page can ask for the "join us" prompt (anonymous visitors only).
export default function PublicLayout() {
  const config = usePublicConfig(); // consent mode and analytics switch from the server
  return (
    <ConsentProvider mode={config.mode}>
      <PublicFrame config={config} />
    </ConsentProvider>
  );
}

function PublicFrame({ config }) {
  const { pathname } = useLocation();
  const main = useRef(null);
  const consent = useConsent();
  // One anonymous page view per route change (never staff, never excluded pages, honours DNT/GPC, the footer switch and
  // the consent choice). Nothing is sent until the server's consent mode is known.
  useTracker({ configReady: config.loaded, mode: config.mode, enabled: config.analyticsEnabled, version: consent.version });

  // New page: scroll to the top and move focus to <main> so keyboard and screen-reader users start at the content.
  const first = useRef(true);
  useEffect(() => {
    if (first.current) { first.current = false; return; }
    window.scrollTo?.(0, 0);
    main.current?.focus({ preventScroll: true });
  }, [pathname]);

  return (
    <SignupPromptProvider>
      <div className="public-shell">
        <a className="skip-link" href="#main" onClick={(e) => { e.preventDefault(); main.current?.focus(); }}>Skip to content</a>
        <Header />
        <main id="main" ref={main} tabIndex={-1}>
          <Outlet />
        </main>
        <Footer />
        <ConsentBanner />
      </div>
    </SignupPromptProvider>
  );
}
