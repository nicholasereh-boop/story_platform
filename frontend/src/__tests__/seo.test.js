import { describe, expect, it } from "vitest";
import { absoluteUrl, articleJsonLd, pageTitle, safeJsonLd } from "../utils/seo";

describe("safeJsonLd", () => {
  it("escapes < so the data can never close the script tag", () => {
    const out = safeJsonLd({ headline: "</script><script>alert(1)</script>" });
    expect(out).not.toContain("<");
    expect(out).toContain("\\u003c/script");
  });

  it("stays valid JSON that means exactly the same thing", () => {
    const original = { headline: "</script><script>alert(1)", n: 1, nested: { a: ["<b>"] } };
    expect(JSON.parse(safeJsonLd(original))).toEqual(original);
  });

  it("escapes the line separators U+2028 and U+2029", () => {
    const out = safeJsonLd({ t: "a\u2028b\u2029c" });
    expect(out).not.toContain("\u2028");
    expect(out).not.toContain("\u2029");
    expect(JSON.parse(out).t).toBe("a\u2028b\u2029c");
  });
});

describe("absoluteUrl and pageTitle", () => {
  it("adds the origin to paths and keeps absolute URLs", () => {
    expect(absoluteUrl("/media/a.jpg", "https://x.com")).toBe("https://x.com/media/a.jpg");
    expect(absoluteUrl("media/a.jpg", "https://x.com")).toBe("https://x.com/media/a.jpg");
    expect(absoluteUrl("https://cdn.example.com/a.jpg", "https://x.com")).toBe("https://cdn.example.com/a.jpg");
    expect(absoluteUrl("", "https://x.com")).toBeUndefined();
    expect(absoluteUrl(null, "https://x.com")).toBeUndefined();
  });

  it("builds page titles", () => {
    expect(pageTitle("A story", "Site")).toBe("A story — Site");
    expect(pageTitle("", "Site")).toBe("Site");
  });
});

describe("articleJsonLd", () => {
  const story = {
    title: "T", seo_title: "SEO title", seo_description: "Desc", excerpt: "Exc", slug: "t", canonical_path: "/stories/t",
    cover: { url: "/media/c.jpg" }, author: "Nia", published_at: "2026-01-02T00:00:00Z", updated_at: "2026-01-03T00:00:00Z",
  };

  it("describes the story as a schema.org Article with absolute URLs", () => {
    const ld = articleJsonLd(story, { origin: "https://x.com", siteName: "Site" });
    expect(ld["@type"]).toBe("Article");
    expect(ld.headline).toBe("SEO title");
    expect(ld.description).toBe("Desc");
    expect(ld.image).toEqual(["https://x.com/media/c.jpg"]);
    expect(ld.author).toEqual({ "@type": "Person", name: "Nia" });
    expect(ld.mainEntityOfPage["@id"]).toBe("https://x.com/stories/t");
    expect(ld.datePublished).toBe("2026-01-02T00:00:00Z");
  });

  it("leaves out what is missing instead of writing null", () => {
    const ld = articleJsonLd({ title: "T", slug: "t" }, { origin: "https://x.com", siteName: "Site" });
    const json = JSON.parse(JSON.stringify(ld));
    expect("image" in json).toBe(false);
    expect("author" in json).toBe(false);
    expect(json.mainEntityOfPage["@id"]).toBe("https://x.com/stories/t");
  });

  it("caps the headline at 110 characters", () => {
    const ld = articleJsonLd({ title: "x".repeat(300), slug: "t" }, { origin: "https://x.com", siteName: "S" });
    expect(ld.headline).toHaveLength(110);
  });
});
