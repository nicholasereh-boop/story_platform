import { SITE_NAME } from "../config";
import { pageTitle } from "../utils/seo";
import { useDocumentMeta } from "./useDocumentMeta";

// Public-page wrapper around useDocumentMeta: adds the site name to the title, makes the canonical and image
// URLs absolute, and defaults to "index,follow".
//   usePublicMeta({ title, description, path, image, type, robots, jsonLd })
// `title` is the page's own title; leave it out on the home page to get just the site name.
export function usePublicMeta({ title, description, path, image, type, robots = "index,follow", jsonLd, home = false }) {
  const origin = typeof window !== "undefined" ? window.location.origin : "";
  const abs = (value) => (!value ? undefined : /^https?:\/\//i.test(value) ? value : `${origin}${value}`);
  useDocumentMeta({
    title: home ? SITE_NAME : title ? pageTitle(title, SITE_NAME) : undefined,
    ogTitle: title || undefined,
    description,
    canonical: path ? abs(path) : undefined,
    robots,
    image: abs(image),
    type,
    siteName: SITE_NAME,
    jsonLd,
  });
}
