import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../api/public", () => ({ getStories: vi.fn(), getCategories: vi.fn() }));
vi.mock("../api/marketplace", () => ({ listProjects: vi.fn() }));
import { listProjects } from "../api/marketplace";
import { getCategories, getStories } from "../api/public";

const story = (id) => ({ id, slug: `s-${id}`, title: `Story ${id}`, excerpt: `About ${id}`, author: "Ann", published_at: "2026-10-28T06:00:00Z", cover: null, reading_minutes: 4 });
const project = (id) => ({ id, slug: `p-${id}`, title: `Product ${id}`, summary: "Ready-made", cover: null, offers: [{ kind: "backend", price: "49.00", currency: "USD", is_free: false }] });
const stories = (n) => Array.from({ length: n }, (_, i) => story(i + 1));

async function mount(props = {}, { hasNext = false } = {}) {
  vi.resetModules();
  const { default: StoryMoreFeed } = await import("../components/story/StoryMoreFeed");
  getStories.mockResolvedValue({ items: stories(30), pagination: { page: 1, has_next: hasNext } });
  getCategories.mockResolvedValue([{ slug: "fiction", name: "Fiction", story_count: 4 }]);
  listProjects.mockResolvedValue({ items: [project(1), project(2), project(3)], pagination: {} });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(<QueryClientProvider client={client}><MemoryRouter><StoryMoreFeed excludeId={1} {...props} /></MemoryRouter></QueryClientProvider>);
  await screen.findByRole("heading", { name: "Discover more" });
  return view;
}
const hrefs = (c) => [...c.querySelectorAll(".sf-card > a")].map((a) => a.getAttribute("href"));

beforeEach(() => { vi.spyOn(window, "scrollTo").mockImplementation(() => {}); Element.prototype.scrollIntoView = vi.fn(); });
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe("Discover more feed on the story page", () => {
  it("shows wide list cards, never the story being read, with topics and marketplace products mixed in", async () => {
    const { container } = await mount();
    const links = hrefs(container);
    expect(links).not.toContain("/stories/s-1");
    expect(links[0]).toBe("/stories/s-2");
    expect(container.querySelectorAll(".sf-card .sf-thumb").length).toBeGreaterThan(5); // picture beside the text
    expect(container.querySelector(".sf-excerpt").textContent).toBe("About 2");
    expect(screen.getByRole("link", { name: /Fiction/ }).getAttribute("href")).toBe("/categories/fiction");
    expect(container.querySelectorAll(".sf-product").length).toBeGreaterThan(0);
    expect(container.querySelector(".sf-price").textContent).toBe("From $49.00");
  });

  it("shows at most 32 story cards and does not grow as the reader scrolls", async () => {
    let made = 0;
    class CountingObserver { constructor() { made += 1; } observe() {} disconnect() {} }
    vi.stubGlobal("IntersectionObserver", CountingObserver);
    const { container } = await mount();
    expect(container.querySelectorAll(".sf-grid > li:not(.sf-product)").length).toBe(29); // 30 stories, minus the one being read: each shown once
    expect(made).toBe(0); // nothing watches the scroll position any more
    expect(screen.queryByRole("button", { name: "Show more stories" })).toBeNull();
    expect(container.querySelector(".sf-sentinel")).toBeNull();
  });

  it("never repeats a story or a product on the page", async () => {
    const { container } = await mount();
    const all = [...container.querySelectorAll(".sf-card > a")].map((a) => a.getAttribute("href"));
    expect(new Set(all).size).toBe(all.length);
  });

  it("Refresh stories shows other stories and scrolls back to the start of the feed", async () => {
    const { container } = await mount();
    const before = hrefs(container).filter((h) => h.startsWith("/stories/")).slice(0, 5);
    fireEvent.click(screen.getByRole("button", { name: /Refresh stories/ }));
    const after = hrefs(container).filter((h) => h.startsWith("/stories/")).slice(0, 5);
    expect(after).not.toEqual(before);
    expect(Element.prototype.scrollIntoView).toHaveBeenCalled();
    expect(screen.getByRole("status").textContent).toBe("Showing a new set of stories");
  });

  it("the bottom button gives a new set of stories", async () => {
    const { container } = await mount();
    const before = hrefs(container).filter((h) => h.startsWith("/stories/")).slice(0, 5);
    fireEvent.click(screen.getByRole("button", { name: "Show me a new set of stories" }));
    expect(hrefs(container).filter((h) => h.startsWith("/stories/")).slice(0, 5)).not.toEqual(before);
  });
});
