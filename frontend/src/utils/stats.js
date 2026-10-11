// Numbers for the editor status bar.
const WORDS_PER_MINUTE = 200;

export function textStats(text) {
  const clean = String(text ?? "").trim();
  const words = clean ? clean.split(/\s+/).length : 0;
  return { words, characters: clean.length, readingMinutes: words === 0 ? 0 : Math.max(1, Math.ceil(words / WORDS_PER_MINUTE)) };
}
