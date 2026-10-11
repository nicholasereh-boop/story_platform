import { describe, expect, it } from "vitest";
import { ACTION_FAMILIES, cleanParams, describeMetadata, formatValue } from "../utils/audit";

describe("audit helpers", () => {
  it("shows before/after pairs as arrows and keeps everything as text", () => {
    expect(formatValue(["draft", "published"])).toBe("draft → published");
    expect(formatValue([true, false])).toBe("yes → no");
    expect(formatValue(null)).toBe("none");
    expect(formatValue({ is_active: [true, false] })).toBe("is_active: yes → no");
    expect(formatValue("<script>alert(1)</script>")).toBe("<script>alert(1)</script>"); // text only: React escapes it when rendered
  });

  it("shortens very long values", () => {
    const text = formatValue("x".repeat(500));
    expect(text.length).toBeLessThanOrEqual(80);
    expect(text.endsWith("…")).toBe(true);
  });

  it("turns metadata into readable key/value rows", () => {
    expect(describeMetadata({ status_from: "pending", changes: { is_staff: [false, true] } })).toEqual([
      { key: "status from", text: "pending" },
      { key: "changes", text: "is_staff: no → yes" },
    ]);
    expect(describeMetadata(null)).toEqual([]);
    expect(describeMetadata("nope")).toEqual([]);
  });

  it("sends only filters that have a value, plus the page when it is not the first", () => {
    expect(cleanParams({ action: "story.*", actor: "", q: "  ", from: "2026-01-01" }, 1)).toEqual({ action: "story.*", from: "2026-01-01" });
    expect(cleanParams({ action: "" }, 3)).toEqual({ page: 3 });
  });

  it("offers the families the server knows", () => {
    const values = ACTION_FAMILIES.map((a) => a.value);
    for (const family of ["story.*", "media.*", "comment.*", "user.*", "auth.*", "mfa.*", "audit.*"]) expect(values).toContain(family);
  });
});
