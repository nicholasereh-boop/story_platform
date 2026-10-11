import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import SignupPromptModal from "../components/engagement/SignupPromptModal";
import { VIEWS_TRIGGER, dismiss, isBlockedPath, isDismissed, recordPageView } from "./signupPrompt";

// request(reason) asks to show the prompt. Reasons:
//   "like" | "comment"  the visitor clicked Like / Comment: ALWAYS allowed (even inside the quiet period)
//   "read" | "views"    automatic triggers: only if the quiet period is over and none was shown yet in this page session
const SignupPromptContext = createContext({ request: () => false });
export const useSignupPrompt = () => useContext(SignupPromptContext);

export function SignupPromptProvider({ children, pageViewDelayMs = 1500 }) {
  const { user, ready } = useAuth() || {};
  const { pathname } = useLocation();
  const [open, setOpen] = useState(false);
  const autoShown = useRef(false); // an automatic prompt already appeared
  const dismissedHere = useRef(false); // closed in this page session (covers browsers that cannot store the flag)

  // Anonymous visitors on a normal page only. Never on /login, /register, password pages or /admin.
  const eligible = Boolean(ready && !user && !isBlockedPath(pathname));

  const request = useCallback(
    (reason) => {
      if (!eligible) return false;
      const explicit = reason === "like" || reason === "comment";
      if (!explicit) {
        if (autoShown.current || dismissedHere.current || isDismissed()) return false;
        autoShown.current = true;
      }
      setOpen(true);
      return true;
    },
    [eligible]
  );
  const requestRef = useRef(request);
  requestRef.current = request;

  const close = useCallback(() => {
    dismissedHere.current = true;
    dismiss(); // 14 days of quiet (a storage failure is ignored; dismissedHere still covers this page session)
    setOpen(false);
  }, []);

  // A new page closes the prompt (e.g. after clicking its Sign up link).
  useEffect(() => setOpen(false), [pathname]);

  // Trigger (c): the 3rd page view of the session. Each address counts once (also under React StrictMode).
  const lastCounted = useRef(null);
  const thirdView = useRef(false);
  useEffect(() => {
    if (isBlockedPath(pathname)) {
      thirdView.current = false; // an auth page or the admin never gets the prompt, and does not count as a view
      return;
    }
    if (lastCounted.current === pathname) return;
    lastCounted.current = pathname;
    thirdView.current = recordPageView() === VIEWS_TRIGGER; // exactly the 3rd, never "3 or more"
  }, [pathname]);
  useEffect(() => {
    if (!ready || !thirdView.current) return undefined;
    const timer = setTimeout(() => {
      thirdView.current = false;
      requestRef.current("views");
    }, pageViewDelayMs);
    return () => clearTimeout(timer);
  }, [pathname, ready, pageViewDelayMs]);

  const value = useMemo(() => ({ request }), [request]);
  return (
    <SignupPromptContext.Provider value={value}>
      {children}
      {open && eligible && <SignupPromptModal onClose={close} from={pathname} />}
    </SignupPromptContext.Provider>
  );
}
