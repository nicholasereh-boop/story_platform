import { beforeEach, describe, expect, it } from "vitest";
import { renderHook } from "@testing-library/react";
import { applyMeta } from "../utils/documentMeta";
import { useDocumentMeta } from "../hooks/useDocumentMeta";

const meta = (attr, key) => document.head.querySelector(`meta[${attr}="${key}"]`)?.getAttribute("content");
const canonical = () => document.head.querySelector('link[rel="canonical"]')?.getAttribute("href");

const FULL = {
  title: "Story — Site", ogTitle: "Story", description: "A description", canonical: "https://x.com/stories/s", robots: "index,follow",
  image: "https://x.com/media/c.jpg", type: "article", siteName: "Site",
};

beforeEach(() => {
  document.head.innerHTML = "";
  document.title = "Original title";
});

describe("applyMeta", () => {
  it("sets the title, description, canonical, robots, Open Graph and Twitter tags", () => {
    applyMeta(document, FULL);
    expect(document.title).toBe("Story — Site");
    expect(meta("name", "description")).toBe("A description");
    expect(meta("name", "robots")).toBe("index,follow");
    expect(canonical()).toBe("https://x.com/stories/s");
    expect(meta("property", "og:title")).toBe("Story");
    expect(meta("property", "og:description")).toBe("A description");
    expect(meta("property", "og:type")).toBe("article");
    expect(meta("property", "og:url")).toBe("https://x.com/stories/s");
    expect(meta("property", "og:image")).toBe("https://x.com/media/c.jpg");
    expect(meta("name", "twitter:card")).toBe("summary_large_image");
    expect(meta("name", "twitter:title")).toBe("Story");
  });

  it("uses the small Twitter card when there is no image", () => {
    applyMeta(document, { ...FULL, image: undefined });
    expect(meta("name", "twitter:card")).toBe("summary");
    expect(document.head.querySelector('meta[property="og:image"]')).toBeNull();
  });

  it("restores everything: old values come back, tags it created are removed", () => {
    document.head.innerHTML = '<meta name="description" content="Old description"><link rel="canonical" href="https://old.example/">';
    const restore = applyMeta(document, FULL);
    expect(meta("name", "description")).toBe("A description");
    restore();
    expect(document.title).toBe("Original title");
    expect(meta("name", "description")).toBe("Old description");
    expect(canonical()).toBe("https://old.example/");
    expect(document.head.querySelector('meta[property="og:title"]')).toBeNull();
    expect(document.head.querySelector('meta[name="robots"]')).toBeNull();
    expect(document.head.querySelectorAll("meta")).toHaveLength(1);
  });

  it("writes noindex for admin-style pages without inventing social tags", () => {
    applyMeta(document, { robots: "noindex, nofollow" });
    expect(meta("name", "robots")).toBe("noindex, nofollow");
    expect(document.head.querySelector('meta[property="og:type"]')).toBeNull();
  });

  it("keeps title text and attributes as text, never as HTML", () => {
    applyMeta(document, { ...FULL, title: '<img src=x onerror="alert(1)">', description: '"><script>alert(1)</script>' });
    expect(document.head.querySelector("img")).toBeNull();
    expect(document.head.querySelector("script")).toBeNull();
    expect(meta("name", "description")).toBe('"><script>alert(1)</script>');
  });

  it("adds JSON-LD that cannot break out of its script tag, and removes it on restore", () => {
    const nasty = "</script><script>alert(1)";
    const restore = applyMeta(document, { ...FULL, jsonLd: { "@type": "Article", headline: nasty } });
    const scripts = document.head.querySelectorAll("script");
    expect(scripts).toHaveLength(1); // nothing was injected
    expect(scripts[0].type).toBe("application/ld+json");
    expect(scripts[0].textContent).not.toContain("<");
    expect(JSON.parse(scripts[0].textContent).headline).toBe(nasty); // same data, safely encoded
    restore();
    expect(document.head.querySelectorAll("script")).toHaveLength(0);
  });
});

describe("useDocumentMeta", () => {
  it("applies on mount and restores on unmount", () => {
    const { unmount } = renderHook(() => useDocumentMeta(FULL));
    expect(document.title).toBe("Story — Site");
    expect(canonical()).toBe("https://x.com/stories/s");
    unmount();
    expect(document.title).toBe("Original title");
    expect(canonical()).toBeUndefined();
  });

  it("updates when the values change (route change) without leaving old tags behind", () => {
    const { rerender } = renderHook((props) => useDocumentMeta(props), { initialProps: FULL });
    rerender({ title: "Other — Site", description: "Another", canonical: "https://x.com/stories/o", robots: "noindex,follow" });
    expect(document.title).toBe("Other — Site");
    expect(meta("name", "description")).toBe("Another");
    expect(meta("name", "robots")).toBe("noindex,follow");
    expect(document.head.querySelector('meta[property="og:image"]')).toBeNull();
    expect(document.head.querySelectorAll('link[rel="canonical"]')).toHaveLength(1);
  });

  it("does nothing when the values are the same object content (no churn)", () => {
    const { rerender } = renderHook((props) => useDocumentMeta(props), { initialProps: { ...FULL } });
    rerender({ ...FULL });
    expect(document.head.querySelectorAll('meta[name="description"]')).toHaveLength(1);
  });
});
