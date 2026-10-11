import { useCallback, useEffect, useRef, useState } from "react";
import { backoffDelay, debounce } from "../utils/autosave";

// Debounced autosave with ONE request in flight at a time.
//
//   getChanges()      -> object of changed fields (empty = nothing to save). Called when a save actually STARTS,
//                        so a queued save always sends the latest data.
//   send(payload)     -> Promise (the autosave PATCH)
//   onSaved(payload, result), onFailed(err)
//   enabled           autosave only runs while true
//
// Returns { status, savedAt, trigger, cancel, exclusive }:
//   status    "idle" | "saving" | "saved" | "retrying" | "failed"
//   trigger() call on every edit (restarts the 3 s timer)
//   exclusive(fn) run any other request (the manual Save) in the same queue, so two never overlap
//
// Network/server errors retry with backoff (3s, 6s, 12s ... max 30s) and local changes are never discarded.
// Validation/permission errors (400/401/403/404) do not retry: the person must fix something first.
const NO_RETRY = [400, 401, 403, 404];

export function useAutosave({ enabled, getChanges, send, onSaved, onFailed, delay = 3000 }) {
  const [status, setStatus] = useState("idle");
  const [savedAt, setSavedAt] = useState(null);
  const live = useRef({});
  live.current = { enabled, getChanges, send, onSaved, onFailed };
  const chain = useRef(Promise.resolve());
  const retryTimer = useRef(null);
  const attempt = useRef(0);
  const debouncer = useRef(null);

  const exclusive = useCallback((fn) => {
    const run = chain.current.then(() => fn());
    chain.current = run.catch(() => {}); // a failure must not block the queue
    return run;
  }, []);

  const hasChanges = () => Object.keys(live.current.getChanges()).length > 0;

  const run = useCallback(() => {
    exclusive(async () => {
      if (!live.current.enabled) return;
      const payload = live.current.getChanges();
      if (Object.keys(payload).length === 0) return;
      setStatus("saving");
      try {
        const result = await live.current.send(payload);
        attempt.current = 0;
        live.current.onSaved(payload, result);
        setStatus("saved");
        setSavedAt(Date.now());
        if (hasChanges()) debouncer.current.call(); // edited while saving: go again
      } catch (err) {
        live.current.onFailed?.(err);
        if (err.status && NO_RETRY.includes(err.status)) {
          setStatus("failed");
        } else {
          setStatus("retrying");
          retryTimer.current = setTimeout(run, backoffDelay(attempt.current));
          attempt.current += 1;
        }
      }
    });
  }, [exclusive]);

  if (!debouncer.current) debouncer.current = debounce(() => run(), delay);

  const cancel = useCallback(() => {
    debouncer.current.cancel();
    clearTimeout(retryTimer.current);
    attempt.current = 0;
  }, []);

  const trigger = useCallback(() => {
    if (!live.current.enabled) return;
    clearTimeout(retryTimer.current); // a new edit restarts the cycle with fresh data
    debouncer.current.call();
  }, []);

  useEffect(() => cancel, [cancel]); // stop timers on unmount

  return { status, savedAt, trigger, cancel, exclusive, setStatus };
}
