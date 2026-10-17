import { useEffect, useRef } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { useTracker } from "../analytics/useTracker";
import Footer from "../components/public/Footer";
import Header from "../components/public/Header";
import { SignupPromptProvider } from "../engagement/SignupPromptContext";

// Frame of every public page: skip link, header, <main>, footer. Routes inside it fill <main>.
// SignupPromptProvider wraps it all so any page can ask for the "join us" prompt (anonymous visitors only).
export default function PublicLayout() {
  const { pathname } = useLocation();
  const main = useRef(null);
  useTracker(); // one anonymous page view per route change (never staff, never excluded pages, honours opt-out)

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
      </div>
    </SignupPromptProvider>
  );
}
