// Small, framework-free helpers behind autosave so they can be unit tested.

/**
 * Debounce with cancel/flush. `call()` restarts the timer; `fn` runs once `delay` ms after the LAST call.
 */
export function debounce(fn, delay) {
  let timer = null;
  const api = {
    call(...args) {
      clearTimeout(timer);
      timer = setTimeout(() => {
        timer = null;
        fn(...args);
      }, delay);
    },
    cancel() {
      clearTimeout(timer);
      timer = null;
    },
    pending: () => timer !== null,
  };
  return api;
}

/** Wait time before retry number `attempt` (0, 1, 2 ...): 3s, 6s, 12s ... capped at 30s. */
export const backoffDelay = (attempt, base = 3000, max = 30000) => Math.min(max, base * 2 ** attempt);

/** The keys whose value differs between `saved` and `current` (deep compare through JSON). */
export function changedKeys(saved, current, keys) {
  if (!saved) return [];
  return keys.filter((key) => JSON.stringify(saved[key]) !== JSON.stringify(current[key]));
}

/** Payload for a PATCH: only the changed fields. */
export function pickChanged(saved, current, keys) {
  const out = {};
  changedKeys(saved, current, keys).forEach((key) => {
    out[key] = current[key];
  });
  return out;
}
