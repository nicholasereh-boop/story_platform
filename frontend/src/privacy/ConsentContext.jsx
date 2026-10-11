import { createContext, useCallback, useContext, useMemo, useState } from "react";
import { cleanMode, needsChoice, readConsent, writeConsent } from "./consent";

// A no-op default, so components such as the footer also work in tests and outside the public layout.
const ConsentContext = createContext({ mode: "notice", choice: null, version: 0, bannerOpen: false, accept() {}, reject() {}, reopen() {} });

// Holds the visitor's analytics choice for the public site. The choice itself is kept only in this browser (consent.js).
export function ConsentProvider({ mode, children }) {
  const safeMode = cleanMode(mode);
  const [choice, setChoice] = useState(() => readConsent());
  const [reopened, setReopened] = useState(false);
  const [version, setVersion] = useState(0); // bumps on every choice so the tracker can re-check

  const decide = useCallback((next) => {
    writeConsent(next); // if storage is blocked the choice still holds for this page (see consent.js)
    setChoice(next);
    setReopened(false);
    setVersion((v) => v + 1);
  }, []);

  const value = useMemo(
    () => ({
      mode: safeMode,
      choice,
      version,
      // The banner shows while a choice is missing, or when the visitor reopens it from the footer.
      bannerOpen: needsChoice(safeMode, choice) || (reopened && safeMode !== "notice"),
      accept: () => decide("accepted"),
      reject: () => decide("rejected"),
      reopen: () => setReopened(true),
    }),
    [safeMode, choice, version, reopened, decide]
  );
  return <ConsentContext.Provider value={value}>{children}</ConsentContext.Provider>;
}

export const useConsent = () => useContext(ConsentContext);
