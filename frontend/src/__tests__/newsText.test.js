import { describe, expect, it } from "vitest";
import { BLOCKER_TEXT, errorText, explainBlocker, formatDate, localToIso } from "../features/news/utils/text";

describe("News text helpers", () => {
  it("explains every blocker the server can send in plain words", () => {
    for (const code of ["no_rights_record", "source_not_approved", "full_text_not_permitted", "commercial_use_not_permitted", "attribution_missing", "edits_not_permitted", "original_link_missing", "body_missing"]) {
      expect(BLOCKER_TEXT[code], code).toBeTruthy();
    }
    expect(explainBlocker("something_new")).toBe("something new");
  });

  it("shows the server's own explanation first", () => {
    expect(errorText({ fieldErrors: { detail: ["Say why the article is withdrawn."] }, friendly: "x" })).toBe("Say why the article is withdrawn.");
    expect(errorText({ fieldErrors: { detail: ["Not allowed."], blockers: ["no_rights_record"] } })).toBe("Not allowed.");
    expect(errorText({ fieldErrors: { blockers: ["no_rights_record", "title_missing"] } })).toContain("no approved rights record");
    expect(errorText({ fieldErrors: { feed_url: ["Feeds must use https."] } })).toBe("feed url: Feeds must use https.");
    expect(errorText({ fieldErrors: {}, friendly: "Cannot reach the server." })).toBe("Cannot reach the server.");
    expect(errorText(null)).toMatch(/went wrong/);
  });

  it("formats dates and datetime-local values safely", () => {
    expect(formatDate("")).toBe("");
    expect(formatDate("not a date")).toBe("");
    expect(formatDate("2026-11-03T09:00:00Z")).toMatch(/2026/);
    expect(localToIso("")).toBe("");
    expect(localToIso("garbage")).toBe("");
    expect(localToIso("2026-11-06T14:30")).toMatch(/^2026-11-06T\d\d:30:00\.000Z$/);
  });
});