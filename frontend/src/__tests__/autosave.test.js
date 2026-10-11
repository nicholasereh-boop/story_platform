import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { backoffDelay, changedKeys, debounce, pickChanged } from "../utils/autosave";
import { textStats } from "../utils/stats";

describe("debounce", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("runs once, 3 seconds after the LAST call", () => {
    const fn = vi.fn();
    const d = debounce(fn, 3000);
    d.call(); vi.advanceTimersByTime(2000);
    d.call(); vi.advanceTimersByTime(2000); // 4 s since the first call, 2 s since the last
    expect(fn).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1000);
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it("passes the latest arguments", () => {
    const fn = vi.fn();
    const d = debounce(fn, 100);
    d.call("a"); d.call("b");
    vi.advanceTimersByTime(100);
    expect(fn).toHaveBeenCalledWith("b");
  });

  it("cancel() stops a pending call and pending() reports the state", () => {
    const fn = vi.fn();
    const d = debounce(fn, 100);
    d.call();
    expect(d.pending()).toBe(true);
    d.cancel();
    expect(d.pending()).toBe(false);
    vi.advanceTimersByTime(500);
    expect(fn).not.toHaveBeenCalled();
  });
});

describe("backoffDelay", () => {
  it("doubles from 3 s and stops at 30 s", () => {
    expect([0, 1, 2, 3, 4, 5].map((n) => backoffDelay(n))).toEqual([3000, 6000, 12000, 24000, 30000, 30000]);
  });
});

describe("changed fields", () => {
  const saved = { title: "A", tags: [1, 2], doc: { a: 1 } };
  it("lists only keys whose value changed (deep compare)", () => {
    expect(changedKeys(saved, { title: "A", tags: [1, 2], doc: { a: 2 } }, ["title", "tags", "doc"])).toEqual(["doc"]);
    expect(changedKeys(saved, { title: "A", tags: [1, 2], doc: { a: 1 } }, ["title", "tags", "doc"])).toEqual([]);
  });
  it("pickChanged builds a PATCH body with only the changes", () => {
    expect(pickChanged(saved, { title: "B", tags: [1, 2], doc: { a: 1 } }, ["title", "tags", "doc"])).toEqual({ title: "B" });
  });
  it("reports nothing before a saved snapshot exists", () => {
    expect(changedKeys(null, { title: "x" }, ["title"])).toEqual([]);
  });
});

describe("textStats", () => {
  it("counts words, characters and reading time", () => {
    expect(textStats("")).toEqual({ words: 0, characters: 0, readingMinutes: 0 });
    expect(textStats("one two  three").words).toBe(3);
    expect(textStats("word ".repeat(450)).readingMinutes).toBe(3);
    expect(textStats("short").readingMinutes).toBe(1);
  });
});
