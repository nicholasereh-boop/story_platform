import { safeJsonLd } from "./seo";

// Sets <title>, meta tags, the canonical link and JSON-LD in the document <head> and returns a function that
// puts everything back exactly as it was (existing tags get their old value back, tags we created are removed).
// All values are written with setAttribute/textContent, never as HTML.
export function applyMeta(doc, meta) {
  const undo = [];
  const { title, description, canonical, robots, image, type, ogTitle, siteName, jsonLd } = meta;

  if (title) {
    const previous = doc.title;
    doc.title = title;
    undo.push(() => { doc.title = previous; });
  }

  // Find or create <tag attr="key">, set `valueAttr`, and remember how to undo it.
  const upsert = (tag, attr, key, valueAttr, value) => {
    if (value === undefined || value === null || value === "") return;
    let el = doc.head.querySelector(`${tag}[${attr}="${key}"]`);
    if (el) {
      const previous = el.getAttribute(valueAttr);
      el.setAttribute(valueAttr, value);
      undo.push(() => (previous === null ? el.removeAttribute(valueAttr) : el.setAttribute(valueAttr, previous)));
    } else {
      el = doc.createElement(tag);
      el.setAttribute(attr, key);
      el.setAttribute(valueAttr, value);
      doc.head.appendChild(el);
      undo.push(() => el.remove());
    }
  };
  const named = (name, value) => upsert("meta", "name", name, "content", value);
  const property = (name, value) => upsert("meta", "property", name, "content", value);

  named("description", description);
  named("robots", robots);
  upsert("link", "rel", "canonical", "href", canonical);

  property("og:title", ogTitle || title);
  property("og:description", description);
  property("og:type", title || description ? type || "website" : undefined);
  property("og:url", canonical);
  property("og:image", image);
  property("og:site_name", siteName);

  named("twitter:card", title || description ? (image ? "summary_large_image" : "summary") : undefined);
  named("twitter:title", ogTitle || title);
  named("twitter:description", description);
  named("twitter:image", image);

  if (jsonLd) {
    const script = doc.createElement("script");
    script.type = "application/ld+json";
    script.textContent = safeJsonLd(jsonLd); // text, not HTML; "<" is escaped inside
    doc.head.appendChild(script);
    undo.push(() => script.remove());
  }

  return () => undo.reverse().forEach((fn) => fn());
}
