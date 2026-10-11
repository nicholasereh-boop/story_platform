import { useEffect } from "react";
import { applyMeta } from "../utils/documentMeta";

// Page metadata for a single-page app: sets the title, description, canonical, robots, Open Graph, Twitter card and
// (optionally) JSON-LD while the page is mounted, and restores the previous values when it unmounts.
//
//   useDocumentMeta({ title, description, canonical, robots: "index,follow" | "noindex", image, type, ogTitle, siteName, jsonLd })
//
// Pass an absolute URL for `canonical` and `image`. Every page calls this, so the order of parent/child effects never matters.
export function useDocumentMeta(meta) {
  const key = JSON.stringify(meta); // objects are new on every render; the content is what matters
  useEffect(() => applyMeta(document, JSON.parse(key)), [key]);
}
