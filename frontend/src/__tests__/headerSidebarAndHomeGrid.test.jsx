import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { card, renderAt, resetBrowser } from "./extensionHarness";

vi.mock("../api/client", async (importOriginal) => ({ ...(await importOriginal()), ensureCsrf: vi.fn().mockResolvedValue({}) }));
vi.mock("../api", () => ({ me: vi.fn(() => Promise.reject(new Error("no session"))), login: vi.fn(), logout: vi.fn(), providers: vi.fn().mockResolvedValue({ google: false }) }));
vi.mock("../api/engagement", () => ({ getLikes: vi.fn(), likeStory: vi.fn(), unlikeStory: vi.fn(), listComments: vi.fn(), createComment: vi.fn(), editComment: vi.fn(), deleteComment: vi.fn(), reportComment: vi.fn() }));
vi.mock("../analytics/tracker", async (importOriginal) => ({ ...(await importOriginal()), sendPageView: vi.fn() }));
vi.mock("../api/security", () => ({ getPublicConfig: vi.fn().mockResolvedValue({ site_name: "StoryBoard", consent_mode: "notice", analytics_enabled: false, contact_email: "" }), getPrivacyPolicy: vi.fn() }));
vi.mock("../api/public", () => ({ getStories: vi.fn(), getStory: vi.fn(), getRelatedStories: vi.fn(), getCategories: vi.fn(), getCategoryStories: vi.fn(), getTags: vi.fn(), searchStories: vi.fn() }));

import * as publicApi from "../api/public";
import { AuthProvider } from "../auth/AuthContext";
import Header from "../components/public/Header";

const read = (file) => readFileSync(resolve(process.cwd(), "src", file), "utf8"); // vitest runs from the frontend folder
const css = read("styles/public-responsive.css");

// The text of the block that follows `@media (...)`, found by balancing braces.
function mediaBlock(query) {
  const start = css.indexOf(`@media ${query}`);
  if (start < 0) return "";
  let depth = 0;
  for (let i = css.indexOf("{", start); i < css.length; i += 1) {
    if (css[i] === "{") depth += 1;
    if (css[i] === "}" && --depth === 0) return css.slice(css.indexOf("{", start) + 1, i);
  }
  return "";
}

describe("sidebar menu (tablets and phones)", () => {
  // The real AuthProvider (its network calls are mocked above); wait for it to settle so nothing updates after the test.
  const mount = () => act(async () => { render(<QueryClientProvider client={new QueryClient()}><MemoryRouter><AuthProvider><Header /></AuthProvider></MemoryRouter></QueryClientProvider>); });
  const toggle = () => screen.getByRole("button", { name: "Menu" });
  const menu = () => document.getElementById("site-menu");

  beforeEach(() => {
    document.body.style.overflow = "";
    delete window.matchMedia;
  });

  it("lists every navigation link, with the current page marked", async () => {
    await mount();
    const nav = screen.getByRole("navigation", { name: "Main" });
    expect([...nav.querySelectorAll("a")].map((a) => a.textContent)).toEqual(["Home", "Stories", "Categories", "Tags", "Marketplace", "Video tools"]);
    expect(nav.querySelector("a[aria-current='page']").textContent).toBe("Home");
  });

  it("starts closed, and the toggle controls the sidebar", async () => {
    await mount();
    expect(toggle().getAttribute("aria-expanded")).toBe("false");
    expect(toggle().getAttribute("aria-controls")).toBe("site-menu");
    expect(menu().className).not.toContain("open");
  });

  it("opens: marks it open, moves focus inside, and stops the page behind from scrolling", async () => {
    await mount();
    fireEvent.click(toggle());
    expect(toggle().getAttribute("aria-expanded")).toBe("true");
    expect(menu().className).toContain("open");
    expect(document.querySelector(".menu-backdrop")).toBeTruthy();
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Close menu" }));
    expect(document.body.style.overflow).toBe("hidden");
  });

  it("Escape closes it, returns focus to the Menu button and releases the scroll lock", async () => {
    document.body.style.overflow = "scroll";
    await mount();
    fireEvent.click(toggle());
    fireEvent.keyDown(document, { key: "Escape" });
    expect(toggle().getAttribute("aria-expanded")).toBe("false");
    expect(document.activeElement).toBe(toggle());
    expect(document.body.style.overflow).toBe("scroll"); // what it was before, not just cleared
    expect(document.querySelector(".menu-backdrop")).toBeNull();
  });

  it("the Close menu button and the dark backdrop both close it", async () => {
    await mount();
    fireEvent.click(toggle());
    fireEvent.click(screen.getByRole("button", { name: "Close menu" }));
    expect(toggle().getAttribute("aria-expanded")).toBe("false");
    expect(document.activeElement).toBe(toggle());
    fireEvent.click(toggle());
    fireEvent.click(document.querySelector(".menu-backdrop"));
    expect(toggle().getAttribute("aria-expanded")).toBe("false");
    expect(document.body.style.overflow).toBe("");
  });

  it("choosing a link goes there and closes the sidebar", async () => {
    await mount();
    fireEvent.click(toggle());
    fireEvent.click(screen.getByRole("link", { name: "Stories" }));
    await waitFor(() => expect(toggle().getAttribute("aria-expanded")).toBe("false"));
    expect(document.body.style.overflow).toBe("");
  });

  it("keeps keyboard focus inside the open sidebar (Tab wraps both ways)", async () => {
    await mount();
    fireEvent.click(toggle());
    const items = [...menu().querySelectorAll("a[href], button, input")];
    const first = items[0];
    const last = items[items.length - 1];
    expect(first).toBe(screen.getByRole("button", { name: "Close menu" }));
    last.focus();
    fireEvent.keyDown(document, { key: "Tab" });
    expect(document.activeElement).toBe(first);
    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(last);
    toggle().focus(); // focus that slipped outside is pulled back in
    fireEvent.keyDown(document, { key: "Tab" });
    expect(menu().contains(document.activeElement)).toBe(true);
  });

  it("closes by itself when the window grows to desktop width, so the page is never left locked", async () => {
    let onChange;
    window.matchMedia = vi.fn(() => ({ matches: true, addEventListener: (_, fn) => { onChange = fn; }, removeEventListener: vi.fn() }));
    await mount();
    fireEvent.click(toggle());
    expect(window.matchMedia).toHaveBeenCalledWith("(max-width: 1024px)");
    act(() => onChange({ matches: false }));
    expect(toggle().getAttribute("aria-expanded")).toBe("false");
    expect(document.body.style.overflow).toBe("");
  });
});

describe("the stylesheet's breakpoints (jsdom cannot lay pages out, so the rules are checked directly)", () => {
  it("uses one breakpoint, 1024px, for the sidebar in both the CSS and the component", () => {
    const header = read("components/public/Header.jsx");
    expect(header).toContain('"(max-width: 1024px)"');
    expect(mediaBlock("(max-width: 1024px)")).toContain(".site-menu");
    expect(mediaBlock("(min-width: 1025px)")).toContain(".home-latest .story-grid");
  });

  it("turns the menu into a fixed right-hand sidebar that is unreachable while closed", () => {
    const small = mediaBlock("(max-width: 1024px)");
    expect(small).toMatch(/\.site-header \.menu-toggle \{ display: inline-flex; \}/);
    expect(small).toMatch(/\.site-header \.site-menu \{[^}]*position: fixed;[^}]*right: 0;[^}]*transform: translateX\(105%\);[^}]*visibility: hidden;/s);
    expect(small).toMatch(/\.site-menu\.open \{[^}]*transform: none;[^}]*visibility: visible;/s);
  });

  it("changes nothing on desktop: the sidebar-only pieces are hidden there", () => {
    const outside = css.replace(mediaBlock("(max-width: 1024px)"), "");
    expect(outside).toMatch(/\.site-header \.menu-close, \.site-header \.menu-backdrop \{ display: none; \}/);
    expect(outside).not.toMatch(/position: fixed/); // no fixed sidebar rule outside the tablet-and-below block
  });

  it("shows one story per row by default and four per row from 1025px up", () => {
    const base = css.replace(mediaBlock("(min-width: 1025px)"), "");
    expect(base).toMatch(/\.home-latest \.story-grid \{ grid-template-columns: minmax\(0, 1fr\); \}/);
    expect(mediaBlock("(min-width: 1025px)")).toMatch(/\.home-latest \.story-grid \{[^}]*repeat\(4, minmax\(0, 1fr\)\)/);
  });

  it("respects people who ask for less motion", () => {
    expect(mediaBlock("(prefers-reduced-motion: reduce)")).toContain("transition: none");
  });
});

describe("home page latest stories", () => {
  beforeEach(() => {
    resetBrowser();
    const stories = Array.from({ length: 9 }, (_, i) => card({ id: i + 1, slug: `s-${i + 1}`, title: `Story ${i + 1}`, cover: null, offers: undefined }));
    publicApi.getStories.mockImplementation(async (params) => ({ items: params?.featured ? [stories[0]] : stories, pagination: { count: 9, page: 1, page_size: 9, total_pages: 1, has_next: false, has_previous: false } }));
    publicApi.getCategories.mockResolvedValue([]);
    publicApi.getTags.mockResolvedValue([]);
  });

  it("puts the latest stories in the responsive grid: 8 cards, which is two full rows of four", async () => {
    const { container } = renderAt("/");
    await screen.findByRole("heading", { name: "Latest stories" });
    const section = container.querySelector("section.home-latest");
    expect(section).toBeTruthy();
    expect(section.querySelectorAll(".story-grid > li").length).toBe(8);
  });

  it("uses the same grid for the loading placeholders so nothing jumps when stories arrive", async () => {
    publicApi.getStories.mockReturnValue(new Promise(() => {}));
    const { container } = renderAt("/");
    await waitFor(() => expect(container.querySelector(".home-latest .story-grid")).toBeTruthy());
    expect(container.querySelectorAll(".home-latest .story-grid > li").length).toBe(8);
  });
});
