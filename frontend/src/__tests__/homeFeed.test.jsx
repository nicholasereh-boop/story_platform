import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import HomeFeed from "../components/home/HomeFeed";
import { buildBatch, buildStream, takeCircular, timeAgo } from "../utils/homeFeed";

const story = (id) => ({ id, slug: `s-${id}`, title: `Story ${id}`, author: "Ann", published_at: "2026-10-28T06:00:00Z", cover: null, reading_minutes: 3 });
const product = (id) => ({ id, slug: `p-${id}`, title: `Product ${id}`, cover: null, offers: [{ kind: "backend", price: "49.00", currency: "USD", is_free: false }] });
const stories = (n) => Array.from({ length: n }, (_, i) => story(i + 1));
const products = (n) => Array.from({ length: n }, (_, i) => product(i + 1));
const cats = [{ slug: "fiction", name: "Fiction", story_count: 4 }, { slug: "essays", name: "Essays", story_count: 9 }];

const ids = (container, sel) => [...container.querySelectorAll(sel)].map((a) => a.getAttribute("href"));
function show(props) {
  const client = new QueryClient();
  return render(<QueryClientProvider client={client}><MemoryRouter><HomeFeed {...props} /></MemoryRouter></QueryClientProvider>);
}

describe("feed rules", () => {
  it("wraps around the end of a list and never repeats an item inside one answer", () => {
    expect(takeCircular([1, 2, 3], 2, 3)).toEqual([3, 1, 2]);
    expect(takeCircular([1, 2], 0, 5)).toEqual([1, 2]);
    expect(takeCircular([], 0, 3)).toEqual([]);
  });

  it("fills the layout: up to 5 in the big card, 4 smaller cards, and a different set after every refresh", () => {
    const a = buildBatch(stories(30), products(10), 0);
    expect(a.hero.length).toBe(5);
    expect(a.small.length).toBe(4);
    expect(a.products.length).toBe(4);
    const b = buildBatch(stories(30), products(10), 1);
    const first = new Set([...a.hero, ...a.small].map((s) => s.id));
    expect([...b.hero, ...b.small].every((s) => !first.has(s.id))).toBe(true); // other stories
    expect(b.products.map((p) => p.id)).not.toEqual(a.products.map((p) => p.id)); // other products
  });

  it("still works with very few stories", () => {
    const one = buildBatch(stories(1), [], 0);
    expect(one.hero.length).toBe(1);
    expect(one.small).toEqual([]);
    const three = buildBatch(stories(3), [], 0);
    expect(three.hero.length + three.small.length).toBe(3);
    expect(buildBatch([], [], 0).hero).toEqual([]);
  });

  it("says how long ago, in short form", () => {
    const now = new Date("2026-10-28T12:00:00Z").getTime();
    expect(timeAgo("2026-10-28T11:30:00Z", now)).toBe("30m");
    expect(timeAgo("2026-10-28T09:00:00Z", now)).toBe("3h");
    expect(timeAgo("2026-10-25T12:00:00Z", now)).toBe("3d");
    expect(timeAgo(null, now)).toBe("");
  });
});

describe("stream of cards under the first rows", () => {
  it("only shows loaded stories while more pages exist, and wraps around once everything is loaded", () => {
    const pool = stories(10);
    const partial = buildStream(pool, { start: 9, count: 12, exhausted: false });
    expect(partial.map((e) => e.story.id)).toEqual([10]); // just what is already there
    const complete = buildStream(pool, { start: 9, count: 12, exhausted: true });
    expect(complete.length).toBe(12);
    expect(complete.map((e) => e.story.id).slice(0, 3)).toEqual([10, 1, 2]);
    expect(new Set(complete.map((e) => e.key)).size).toBe(12); // unique keys even when a story comes round again
  });

  it("mixes one marketplace product in after every 7 stories, and rotates through the products", () => {
    const out = buildStream(stories(40), { start: 0, count: 24, exhausted: true, products: products(3), productStart: 0 });
    const kinds = out.map((e) => e.type);
    expect(kinds.filter((k) => k === "product").length).toBe(3);
    expect(kinds.indexOf("product")).toBe(7);
    expect(out.filter((e) => e.type === "product").map((e) => e.project.id)).toEqual([1, 2, 3]);
    expect(buildStream([], { start: 0, count: 5, exhausted: true })).toEqual([]);
  });
});

describe("home feed", () => {
  beforeEach(() => { vi.useFakeTimers(); vi.spyOn(window, "scrollTo").mockImplementation(() => {}); });
  afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

  it("shows a big card, two cards beside it, a second row, and marketplace products", () => {
    const { container } = show({ stories: stories(20), products: products(8), categories: cats });
    expect(container.querySelectorAll(".hf-hero").length).toBe(1);
    expect(ids(container, ".hf-card > a").slice(0, 4)).toEqual(["/stories/s-6", "/stories/s-7", "/stories/s-8", "/stories/s-9"]);
    expect(screen.getByRole("heading", { name: /Suggested for you/ })).toBeTruthy();
    expect(screen.getByRole("heading", { name: /Source code/ })).toBeTruthy();
    expect(ids(container, ".hf-tiles a")).toEqual(["/marketplace/projects/p-1", "/marketplace/projects/p-2", "/marketplace/projects/p-3", "/marketplace/projects/p-4"]);
    expect(container.querySelector(".hf-tile-price").textContent).toBe("From $49.00");
  });

  it("changes the big card to the next story by itself and has arrows and dots", () => {
    const { container } = show({ stories: stories(20), products: [], categories: [] });
    const title = () => container.querySelector(".hf-slide.is-active .hf-hero-title").textContent;
    expect(title()).toBe("Story 1");
    act(() => { vi.advanceTimersByTime(6000); });
    expect(title()).toBe("Story 2");
    fireEvent.click(screen.getByLabelText("Next story"));
    expect(title()).toBe("Story 3");
    fireEvent.click(screen.getByLabelText("Show story 1 of 5"));
    expect(title()).toBe("Story 1");
    fireEvent.click(screen.getByLabelText("Pause top stories"));
    act(() => { vi.advanceTimersByTime(20000); });
    expect(title()).toBe("Story 1");
  });

  it("Refresh stories swaps in other stories and other products", () => {
    const { container } = show({ stories: stories(30), products: products(10), categories: cats });
    const before = ids(container, ".hf-card > a").slice(0, 4);
    const productsBefore = ids(container, ".hf-tiles a");
    const heroBefore = container.querySelector(".hf-slide.is-active").getAttribute("href");
    fireEvent.click(screen.getByRole("button", { name: /Refresh stories/ }));
    const after = ids(container, ".hf-card > a").slice(0, 4);
    expect(after).not.toEqual(before);
    expect(after.some((h) => before.includes(h))).toBe(false);
    expect(container.querySelector(".hf-slide.is-active").getAttribute("href")).not.toBe(heroBefore);
    expect(ids(container, ".hf-tiles a")).not.toEqual(productsBefore);
    expect(ids(container, ".hf-tiles a").length).toBe(4); // products come with every refreshed page
    expect(screen.getByRole("status").textContent).toBe("Showing a new set of stories");
  });

  it("shows no product box when there are no products", () => {
    show({ stories: stories(12), products: [], categories: cats });
    expect(screen.queryByRole("heading", { name: /Source code/ })).toBeNull();
  });

  it("shows one page of 32 cards and does not grow when the reader scrolls", () => {
    class FakeObserver { constructor() { FakeObserver.made += 1; } observe() {} disconnect() {} }
    FakeObserver.made = 0;
    vi.stubGlobal("IntersectionObserver", FakeObserver);
    const { container } = show({ stories: stories(60), products: products(10), categories: cats });
    const cards = container.querySelectorAll(".hf-grid > li:not(.hf-widget)");
    expect(cards.length).toBe(32);
    expect(container.querySelectorAll(".hf-product").length).toBe(3);
    expect(FakeObserver.made).toBe(0); // nothing watches the scroll position any more
    expect(screen.queryByRole("button", { name: "Show more stories" })).toBeNull();
    expect(container.querySelector(".hf-sentinel")).toBeNull();
  });

  it("never shows the same marketplace product twice on the page", () => {
    for (const n of [1, 2, 4, 5, 7, 10]) {
      const { container, unmount } = show({ stories: stories(60), products: products(n), categories: cats });
      const all = ids(container, ".hf-tiles a, .hf-product > a");
      expect(new Set(all).size).toBe(all.length);
      unmount();
    }
  });

  it("shows only the stories a small site has, without repeating any card", () => {
    const links = (container) => [...container.querySelectorAll(".hf-slide, .hf-card > a")].map((a) => a.getAttribute("href"));
    for (const n of [1, 3, 9, 10, 14, 30]) {
      const { container, unmount } = show({ stories: stories(n), products: [], categories: [] });
      const all = links(container);
      expect(new Set(all).size).toBe(all.length); // no story twice on the page
      expect(all.length).toBe(n < 33 ? n : 33);
      unmount();
    }
  });

  it("a refresh on a small site still shows each story only once", () => {
    const { container } = show({ stories: stories(14), products: [], categories: [] });
    fireEvent.click(screen.getByRole("button", { name: /Refresh stories/ }));
    const all = [...container.querySelectorAll(".hf-slide, .hf-card > a")].map((a) => a.getAttribute("href"));
    expect(new Set(all).size).toBe(all.length);
    expect(all.length).toBe(14);
  });

  it("asks for the next page of stories when too few are loaded to fill the page", () => {
    const onLoadMore = vi.fn();
    show({ stories: stories(12), hasMore: true, onLoadMore });
    expect(onLoadMore).toHaveBeenCalled();
  });

  it("the bottom button gives a new set of stories", () => {
    const { container } = show({ stories: stories(60), products: [], categories: [] });
    const titles = () => [...container.querySelectorAll(".hf-card-title")].map((n) => n.textContent).join("|");
    const before = titles();
    fireEvent.click(screen.getByRole("button", { name: "Show me a new set of stories" }));
    expect(titles()).not.toBe(before);
  });
});
