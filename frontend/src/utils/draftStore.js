// Crash protection: a copy of the unsaved form kept in sessionStorage (this tab only, gone when the tab closes),
// one entry per story id ("new" for an unsaved new story). Never holds passwords or tokens.
// Every call is wrapped because storage can be full or blocked (private windows).
const keyFor = (id) => `storyboard:draft:${id}`;

export function readDraft(id) {
  try {
    const raw = sessionStorage.getItem(keyFor(id));
    const parsed = raw ? JSON.parse(raw) : null;
    return parsed && parsed.form && typeof parsed.savedAt === "number" ? parsed : null;
  } catch {
    return null;
  }
}

export function writeDraft(id, form) {
  try {
    sessionStorage.setItem(keyFor(id), JSON.stringify({ savedAt: Date.now(), form }));
  } catch {
    /* storage unavailable: autosave to the server still protects the work */
  }
}

export function clearDraft(id) {
  try {
    sessionStorage.removeItem(keyFor(id));
  } catch {
    /* ignore */
  }
}
