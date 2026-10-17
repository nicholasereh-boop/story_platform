// Pure helpers for page metadata. No DOM here, so they are easy to test.

/** "Story title — StoryBoard"; the bare site name for the home page. */
export const pageTitle = (title, siteName) => (title ? `${title} — ${siteName}` : siteName);

/** Make a path or URL absolute: "/media/a.jpg" -> "https://site.com/media/a.jpg". Absolute URLs are kept. */
export function absoluteUrl(value, origin) {
  if (!value) return undefined;
  if (/^https?:\/\//i.test(value)) return value;
  return `${origin}${value.startsWith("/") ? "" : "/"}${value}`;
}

/**
 * Serialise a plain object for a <script type="application/ld+json"> tag.
 * "<" is escaped as \u003c so a title such as "</script><script>alert(1)" can never close the tag and inject markup
 * (the JSON stays valid and means the same thing). U+2028/2029 are escaped too (they break older JS parsers).
 */
export function safeJsonLd(object) {
  return JSON.stringify(object)
    .replace(/</g, "\\u003c")
    .replace(/\u2028/g, "\\u2028")
    .replace(/\u2029/g, "\\u2029");
}

/** schema.org Article for a story from the public API. */
export function articleJsonLd(story, { origin, siteName }) {
  const image = absoluteUrl(story.cover?.url, origin);
  return {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: (story.seo_title || story.title || "").slice(0, 110),
    description: story.seo_description || story.excerpt || undefined,
    image: image ? [image] : undefined,
    datePublished: story.published_at || undefined,
    dateModified: story.updated_at || story.published_at || undefined,
    author: story.author ? { "@type": "Person", name: story.author } : undefined,
    publisher: { "@type": "Organization", name: siteName },
    mainEntityOfPage: { "@type": "WebPage", "@id": `${origin}${story.canonical_path || `/stories/${story.slug}`}` },
  };
}
