// YouTube id extraction. This is a direct port of the server's rules (apps/stories/content.py::youtube_id),
// so anything accepted here is accepted by the backend and vice versa.
const YT_ID = /^[A-Za-z0-9_-]{11}$/;
const YT_URL =
  /^https:\/\/(?:www\.|m\.)?(?:youtube\.com\/(?:watch\?(?:[^#]*&)?v=|embed\/|shorts\/)|youtube-nocookie\.com\/embed\/|youtu\.be\/)([A-Za-z0-9_-]{11})(?:[&?#/].*)?$/;

/** The 11-character video id from a YouTube URL (https only) or a bare id; otherwise null. */
export function extractYoutubeId(value) {
  const text = String(value ?? "").trim();
  if (YT_ID.test(text)) return text;
  const match = YT_URL.exec(text);
  return match ? match[1] : null;
}

/** Privacy-friendly embed address (no cookies until the visitor presses play). */
export const youtubeEmbedUrl = (videoId) => `https://www.youtube-nocookie.com/embed/${videoId}`;
