import { describe, expect, it } from "vitest";
import { isSafeHref, normalizeLink } from "../utils/links";

describe("isSafeHref", () => {
  it("allows http, https and mailto in any letter case", () => {
    expect(isSafeHref("https://example.com/a?b=1#c")).toBe(true);
    expect(isSafeHref("http://example.com")).toBe(true);
    expect(isSafeHref("HTTPS://EXAMPLE.COM")).toBe(true);
    expect(isSafeHref("mailto:me@example.com")).toBe(true);
  });

  it("rejects dangerous or unknown schemes", () => {
    ["javascript:alert(1)", "JaVaScRiPt:alert(1)", "data:text/html,hi", "vbscript:x", "ftp://example.com", "//example.com", "/relative"]
      .forEach((href) => expect(isSafeHref(href)).toBe(false));
  });

  it("rejects whitespace and control characters (nothing is trimmed)", () => {
    expect(isSafeHref(" https://example.com")).toBe(false);
    expect(isSafeHref("https://exa mple.com")).toBe(false);
    expect(isSafeHref("https://example.com\n")).toBe(false);
    expect(isSafeHref("java\tscript:alert(1)")).toBe(false);
  });

  it("rejects empty, non-string and over-long values", () => {
    expect(isSafeHref("")).toBe(false);
    expect(isSafeHref(null)).toBe(false);
    expect(isSafeHref(`https://e.com/${"a".repeat(2000)}`)).toBe(false);
  });
});

describe("normalizeLink", () => {
  it("adds https:// to bare domains and mailto: to email addresses", () => {
    expect(normalizeLink("example.com")).toBe("https://example.com");
    expect(normalizeLink("  example.com/path ")).toBe("https://example.com/path");
    expect(normalizeLink("me@example.com")).toBe("mailto:me@example.com");
  });

  it("keeps valid links as they are", () => {
    expect(normalizeLink("https://example.com")).toBe("https://example.com");
    expect(normalizeLink("mailto:me@example.com")).toBe("mailto:me@example.com");
  });

  it("returns null for unsafe or empty input", () => {
    expect(normalizeLink("javascript:alert(1)")).toBeNull();
    expect(normalizeLink("data:text/html,hi")).toBeNull();
    expect(normalizeLink("two words")).toBeNull();
    expect(normalizeLink("   ")).toBeNull();
  });
});
