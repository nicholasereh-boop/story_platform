import { describe, expect, it } from "vitest";
import { KPIS, formatChange, pointLabel, share } from "../utils/analytics";

describe("formatChange", () => {
  it("says so when there is nothing to compare with", () => {
    for (const none of [null, undefined]) {
      const c = formatChange(none);
      expect(c.direction).toBe("none");
      expect(c.text).toBe("No previous data");
    }
  });
  it("shows an up arrow, a down arrow or no change, always with words for screen readers", () => {
    expect(formatChange(12.5)).toMatchObject({ direction: "up", text: "▲ 12.5%", spoken: "Up 12.5% from the previous period" });
    expect(formatChange(-3)).toMatchObject({ direction: "down", text: "▼ 3%", spoken: "Down 3% from the previous period" });
    expect(formatChange(0)).toMatchObject({ direction: "flat", text: "No change" });
    expect(formatChange(100).text).toBe("▲ 100%");
  });
});

describe("labels and shares", () => {
  it("labels days, weeks and months", () => {
    expect(pointLabel("2026-03-05", "day")).toBe("Mar 5");
    expect(pointLabel("2026-03-02", "week")).toBe("Week of Mar 2");
    expect(pointLabel("2026-03-01", "month")).toBe("Mar 2026");
  });
  it("computes whole-percent shares without dividing by zero", () => {
    expect(share(1, 3)).toBe(33);
    expect(share(0, 0)).toBe(0);
  });
  it("lists the six tiles in order", () => {
    expect(KPIS.map((k) => k.key)).toEqual(["unique_visitors", "page_views", "story_views", "registered_users", "likes", "comments"]);
  });
});
