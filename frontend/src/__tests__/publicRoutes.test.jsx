import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createMemoryRouter } from "react-router-dom";

// The visitor is NOT logged in and the CSRF/me calls FAIL: the public site must still work.
vi.mock("../api/client", async (importOriginal) => ({
  ...(await importOriginal()),
  ensureCsrf: vi.fn().mockRejectedValue(new Error("backend down")),
}));
vi.mock("../api", () => ({
  me: vi.fn().mockRejectedValue(new Error("no session")), login: vi.fn(), logout: vi.fn(), providers: vi.fn().mockResolvedValue({ google: false }),
}));
vi.mock("../api/engagement", () => ({
  getLikes: vi.fn(), likeStory: vi.fn(), unlikeStory: vi.fn(), listComments: vi.fn(),
  createComment: vi.fn(), editComment: vi.fn(), deleteComment: vi.fn(), reportComment: vi.fn(),
}));
// Page views must not hit the network in tests.
vi.mock("../analytics/tracker", async (importOriginal) => ({ ...(await importOriginal()), sendPageView: vi.fn() }));
vi.mock("../api/public", () => ({
  getStories: vi.fn(), getStory: vi.fn(), getRelatedStories: vi.fn(), getCategories: vi.fn(),
  getCategoryStories: vi.fn(), getTags: vi.fn(), searchStories: vi.fn(),
}));

// The public layout asks the server for its consent mode and the privacy page for its numbers: answer from here, never the network.
vi.mock("../api/security", () => ({
  getPublicConfig: vi.fn().mockResolvedValue({ site_name: "StoryBoard", consent_mode: "notice", analytics_enabled: true, contact_email: "" }),
  getPrivacyPolicy: vi.fn().mockResolvedValue({
    site_name: "StoryBoard", operator_name: "", contact_email: "hello@example.com", effective_date: "2026-10-01", consent_mode: "notice", analytics_enabled: true,
    retention: { analytics_events_days: 90, analytics_visitors_days: 400, audit_log_days: 365, comment_edit_window_minutes: 15 },
    cookies: [{ name: "sessionid", purpose: "Keeps you logged in.", duration: "14 days", necessary: true }],
  }),
}));

import * as eng from "../api/engagement";
import * as pub from "../api/public";
import { routes } from "../App";

const card = (n) => ({
  id: n, title: `Story number ${n}`, slug: `story-${n}`, excerpt: "An excerpt.", cover: null,
  categories: [{ name: "News", slug: "news" }], tags: [], author: "Nia", published_at: "2026-03-05T10:00:00Z", reading_minutes: 2, is_featured: n === 1, like_count: 0, comment_count: 0,
});
const page = (items) => ({ items, pagination: { count: items.length, page: 1, page_size: 12, total_pages: 1, has_next: false, has_previous: false } });
const detail = {
  ...card(1), seo_title: "SEO title one", seo_description: "SEO description", canonical_path: "/stories/story-1", updated_at: "2026-03-06T10:00:00Z",
  tags: [{ name: "Python", slug: "python" }], like_count: 3, comment_count: 2,
  content_json: { type: "doc", content: [{ type: "paragraph", content: [{ type: "text", text: "Hello reader" }] }] },
};
const notFound = () => Object.assign(new Error("nf"), { status: 404, friendly: "Not found." });

function renderAt(path) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  return render(<QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
  window.scrollTo = vi.fn();
  document.head.innerHTML = "";
  pub.getStories.mockResolvedValue(page([card(1), card(2), card(3)]));
  pub.getCategories.mockResolvedValue([{ name: "News", slug: "news", description: "", story_count: 3 }]);
  pub.getTags.mockResolvedValue([{ name: "Python", slug: "python", story_count: 2 }]);
  pub.getStory.mockResolvedValue(detail);
  pub.getRelatedStories.mockResolvedValue([card(2)]);
  pub.getCategoryStories.mockResolvedValue(page([card(1)]));
  pub.searchStories.mockResolvedValue(page([card(2)]));
  eng.listComments.mockResolvedValue(page([]));
  window.localStorage.clear();
  window.sessionStorage.clear();
});

const h1s = () => screen.getAllByRole("heading", { level: 1 });

describe("public pages without a logged-in user", () => {
  it("home renders with header, footer, one h1, stories, and no Admin link", async () => {
    renderAt("/");
    expect(await screen.findByRole("heading", { name: "Latest stories", level: 2 })).toBeTruthy();
    expect(h1s()).toHaveLength(1);
    expect(screen.getByRole("banner")).toBeTruthy();
    expect(screen.getByRole("main")).toBeTruthy();
    expect(screen.getByRole("contentinfo")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Skip to content" })).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Admin" })).toBeNull();
    expect(document.title).toBe("StoryBoard");
  });

  it("stories list renders the cards and marks the nav link as current", async () => {
    renderAt("/stories");
    expect(await screen.findByText("Story number 2")).toBeTruthy();
    expect(h1s()).toHaveLength(1);
    expect(screen.getAllByRole("link", { name: "Stories" }).some((a) => a.getAttribute("aria-current") === "page")).toBe(true);
  });

  it("story detail renders the body, SEO tags, share buttons and related stories", async () => {
    renderAt("/stories/story-1");
    expect(await screen.findByText("Hello reader")).toBeTruthy();
    expect(h1s()).toHaveLength(1);
    expect(await screen.findByText("Keep reading")).toBeTruthy();
    expect(screen.getByRole("button", { name: /copy link/i })).toBeTruthy();
    await waitFor(() => expect(document.title).toBe("SEO title one — StoryBoard"));
    expect(document.head.querySelector('meta[name="description"]').getAttribute("content")).toBe("SEO description");
    expect(document.head.querySelector('link[rel="canonical"]').getAttribute("href")).toBe(`${window.location.origin}/stories/story-1`);
    expect(document.head.querySelector('script[type="application/ld+json"]')).toBeTruthy();
  });

  it("an unknown story shows the public 404 page and asks search engines not to index it", async () => {
    pub.getStory.mockRejectedValue(notFound());
    renderAt("/stories/nope");
    expect(await screen.findByRole("heading", { name: /story could not be found/i })).toBeTruthy();
    await waitFor(() => expect(document.head.querySelector('meta[name="robots"]').getAttribute("content")).toContain("noindex"));
  });

  it("categories, tags, category and tag pages render", async () => {
    const first = renderAt("/categories");
    expect(await screen.findByRole("link", { name: "News" })).toBeTruthy();
    first.unmount();
    const second = renderAt("/tags");
    expect(await screen.findByRole("link", { name: /Python/ })).toBeTruthy();
    second.unmount();
    const third = renderAt("/categories/news");
    expect(await screen.findByText("Story number 1")).toBeTruthy();
    third.unmount();
    renderAt("/tags/python");
    expect(await screen.findByText("Story number 1")).toBeTruthy();
  });

  it("an unknown category is a public 404", async () => {
    pub.getCategoryStories.mockRejectedValue(notFound());
    renderAt("/categories/nope");
    expect(await screen.findByRole("heading", { name: /category could not be found/i })).toBeTruthy();
  });

  it("search shows a hint for short text and results for a real query", async () => {
    const first = renderAt("/search?q=a");
    expect(await screen.findByText(/at least 2 characters/i)).toBeTruthy();
    expect(pub.searchStories).not.toHaveBeenCalled();
    first.unmount();
    renderAt("/search?q=lamp");
    expect(await screen.findByText(/1 story found/i)).toBeTruthy();
    expect(pub.searchStories).toHaveBeenCalledWith("lamp", { page: 1 });
  });

  it("shows an error with a Try again button when the API fails", async () => {
    pub.getStories.mockRejectedValue(Object.assign(new Error("x"), { status: 500, friendly: "Something went wrong." }));
    renderAt("/stories");
    expect(await screen.findByRole("button", { name: /try again/i })).toBeTruthy();
  });

  it("an unknown address gets the public 404 page", async () => {
    renderAt("/definitely/not/here");
    expect(await screen.findByRole("heading", { name: /could not be found/i })).toBeTruthy();
  });

  it("the admin area still redirects an anonymous visitor to the login page", async () => {
    renderAt("/admin/stories");
    expect(await screen.findByRole("heading", { name: "Log in" })).toBeTruthy();
  });

  it("story page shows the like button, the comments block and the visitor's invitation to log in", async () => {
    renderAt("/stories/story-1");
    expect(await screen.findByText("3 likes")).toBeTruthy();
    expect(await screen.findByRole("heading", { name: /Comments/, level: 2 })).toBeTruthy();
    expect(await screen.findByText(/no comments yet/i)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Log in to join the discussion" })).toBeTruthy();
    expect(eng.getLikes).not.toHaveBeenCalled(); // visitors never ask who liked
    expect(screen.queryByRole("dialog")).toBeNull(); // the prompt is never shown just because a page loaded
  });

  it("a visitor who clicks Like gets the signup prompt, and nothing is sent", async () => {
    renderAt("/stories/story-1");
    fireEvent.click(await screen.findByRole("button", { name: /^like/i }));
    expect(await screen.findByRole("dialog", { name: "Join the conversation" })).toBeTruthy();
    expect(eng.likeStory).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("the header offers Log in and Sign up to visitors", async () => {
    renderAt("/");
    expect(await screen.findByRole("link", { name: "Log in" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Sign up" }).getAttribute("href")).toBe("/register");
  });

  it("the sign-up and password pages exist", async () => {
    const first = renderAt("/register");
    expect(await screen.findByRole("heading", { name: "Create your account" })).toBeTruthy();
    first.unmount();
    const second = renderAt("/forgot-password");
    expect(await screen.findByRole("heading", { name: "Forgot your password?" })).toBeTruthy();
    second.unmount();
    const third = renderAt("/reset-password?uid=a&token=b");
    expect(await screen.findByRole("heading", { name: "Choose a new password" })).toBeTruthy();
    third.unmount();
    renderAt("/account"); // a visitor has no account page: they are asked to log in
    expect(await screen.findByRole("heading", { name: "Log in" })).toBeTruthy();
  });
});
