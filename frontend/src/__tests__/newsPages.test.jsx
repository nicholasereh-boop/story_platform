import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../features/news/api/news", () => ({
  getNewsConfig: vi.fn(), listNewsArticles: vi.fn(), getNewsArticle: vi.fn(), listNewsCategories: vi.fn(), getNewsFeatured: vi.fn(),
  getNewsBreaking: vi.fn(), getNewsRelated: vi.fn(), countNewsView: vi.fn(), submitNewsComplaint: vi.fn(),
}));
import * as api from "../features/news/api/news";
import { buildPublicNewsRoutes } from "../features/news/routes";

const card = (o = {}) => ({ slug: "bridge-vote", title: "Council approves new bridge", standfirst: "Work starts in spring.", author_name: "Ada Obi", published_at: "2026-11-03T09:00:00Z", category: { name: "Politics", slug: "politics" }, source: { name: "Daily Example", slug: "daily-example" }, is_featured: false, is_breaking: false, article_type: "licensed", lead_image: null, ...o });
const detail = (o = {}) => ({ ...card(), body: "<p>The council voted on Tuesday.</p>", language: "en", attribution: "Source: Daily Example. By Ada Obi.", source_published_at: "2026-11-02T08:00:00Z", original_url: "https://example.com/original", counter_required: false, licence: "CC BY 4.0", assets: [], word_count: 5, ...o });
const page = (items) => ({ items, pagination: { count: items.length, page: 1, page_size: 12, total_pages: 1, has_next: false, has_previous: false } });
const err = (fieldErrors) => Object.assign(new Error("x"), { fieldErrors, friendly: "Something went wrong." });

function renderAt(path) {
  const router = createMemoryRouter([...buildPublicNewsRoutes(), { path: "*", element: <p>elsewhere</p> }], { initialEntries: [path] });
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><RouterProvider router={router} /></QueryClientProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
  window.scrollTo = vi.fn();
  api.getNewsConfig.mockResolvedValue({ copyright_contact: "legal@example.com" });
  api.listNewsCategories.mockResolvedValue([{ id: 1, name: "Politics", slug: "politics" }]);
  api.getNewsBreaking.mockResolvedValue([]);
  api.getNewsFeatured.mockResolvedValue([]);
  api.listNewsArticles.mockResolvedValue(page([card()]));
  api.getNewsArticle.mockResolvedValue(detail());
  api.getNewsRelated.mockResolvedValue([card({ slug: "other", title: "Another story" })]);
  api.countNewsView.mockResolvedValue({ counted: true });
});

describe("News home", () => {
  it("shows the latest articles with links to them and to their category", async () => {
    renderAt("/news");
    const link = await screen.findByRole("link", { name: "Council approves new bridge" });
    expect(link.getAttribute("href")).toBe("/news/bridge-vote");
    expect(screen.getAllByRole("link", { name: "Politics" }).some((a) => a.getAttribute("href") === "/news/category/politics")).toBe(true);
  });

  it("shows breaking news and a featured lead above the list", async () => {
    api.getNewsBreaking.mockResolvedValue([card({ slug: "flash", title: "Flash flood warning", is_breaking: true })]);
    api.getNewsFeatured.mockResolvedValue([card({ slug: "big", title: "The big story", is_featured: true })]);
    renderAt("/news");
    expect(await screen.findByRole("link", { name: "Flash flood warning" })).toBeTruthy();
    expect(await screen.findByRole("link", { name: "The big story" })).toBeTruthy();
  });

  it("says so when nothing is published and when loading fails", async () => {
    api.listNewsArticles.mockResolvedValue(page([]));
    renderAt("/news");
    expect(await screen.findByText("No news has been published yet.")).toBeTruthy();
  });

  it("shows a calm error when the news cannot be loaded", async () => {
    api.listNewsArticles.mockRejectedValue(err({}));
    renderAt("/news");
    expect(await screen.findByRole("alert")).toBeTruthy();
  });
});

describe("News list and search", () => {
  it("asks the server for one category", async () => {
    renderAt("/news/category/politics");
    expect(await screen.findByRole("heading", { name: "Politics" })).toBeTruthy();
    await waitFor(() => expect(api.listNewsArticles).toHaveBeenCalledWith(expect.objectContaining({ category: "politics", page: 1 })));
  });

  it("searches, and refuses a one-letter search without calling the server", async () => {
    renderAt("/news/search?q=bridge");
    await waitFor(() => expect(api.listNewsArticles).toHaveBeenCalledWith(expect.objectContaining({ q: "bridge" })));
    api.listNewsArticles.mockClear();
    renderAt("/news/search?q=b");
    expect(await screen.findByText("Type at least two characters to search.")).toBeTruthy();
    expect(api.listNewsArticles).not.toHaveBeenCalled();
  });

  it("the search box sends you to the search page", async () => {
    renderAt("/news");
    const box = await screen.findByLabelText("Search news", { selector: "input" });
    fireEvent.change(box, { target: { value: "weather" } });
    fireEvent.submit(box.closest("form"));
    await waitFor(() => expect(api.listNewsArticles).toHaveBeenCalledWith(expect.objectContaining({ q: "weather" })));
  });
});

describe("News article", () => {
  it("shows the full article with byline, attribution, original link, licence and related stories", async () => {
    renderAt("/news/bridge-vote");
    expect(await screen.findByRole("heading", { name: "Council approves new bridge" })).toBeTruthy();
    expect(screen.getByText("The council voted on Tuesday.")).toBeTruthy();
    expect(screen.getByText(/By Ada Obi/)).toBeTruthy();
    expect(screen.getByText("Source: Daily Example. By Ada Obi.")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Read the original article" }).getAttribute("href")).toBe("https://example.com/original");
    expect(screen.getByText("Licence: CC BY 4.0")).toBeTruthy();
    expect(await screen.findByRole("link", { name: "Another story" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "legal@example.com" }).getAttribute("href")).toBe("mailto:legal@example.com");
    expect(api.countNewsView).not.toHaveBeenCalled(); // this licence does not ask for a counter
  });

  it("counts one view only when the licence requires a counter", async () => {
    api.getNewsArticle.mockResolvedValue(detail({ counter_required: true }));
    renderAt("/news/bridge-vote");
    await screen.findByRole("heading", { name: "Council approves new bridge" });
    await waitFor(() => expect(api.countNewsView).toHaveBeenCalledTimes(1));
    expect(api.countNewsView).toHaveBeenCalledWith("bridge-vote");
  });

  it("shows image credits and captions with each picture", async () => {
    api.getNewsArticle.mockResolvedValue(detail({ assets: [{ id: 1, kind: "image", image: { url: "/media/a.jpg", width: 800, height: 400 }, alt: "The bridge", caption: "The old bridge", credit: "Photo: Bo", creator: "", licence: "CC BY 4.0" }] }));
    renderAt("/news/bridge-vote");
    expect(await screen.findByAltText("The bridge")).toBeTruthy();
    expect(screen.getByText("The old bridge · Photo: Bo · CC BY 4.0")).toBeTruthy();
  });

  it("an unavailable article is a plain not-found page", async () => {
    api.getNewsArticle.mockRejectedValue(Object.assign(err({}), { status: 404 }));
    renderAt("/news/hidden");
    expect(await screen.findByRole("heading", { name: "Article not found" })).toBeTruthy();
    expect(screen.queryByText(/withdrawn|quarantined|rights/i)).toBeNull(); // nothing about WHY it is hidden
  });
});

describe("Report a problem", () => {
  const fill = async () => {
    fireEvent.change(await screen.findByLabelText("Your name"), { target: { value: "Pat" } });
    fireEvent.change(screen.getByLabelText("Your email"), { target: { value: "pat@example.com" } });
    fireEvent.change(screen.getByLabelText("Link to the article"), { target: { value: "https://site.example/news/bridge-vote" } });
    fireEvent.change(screen.getByLabelText("Details"), { target: { value: "This copies my article without permission." } });
  };

  it("sends the report and thanks the sender", async () => {
    api.submitNewsComplaint.mockResolvedValue({ received: true });
    renderAt("/news/report");
    await fill();
    fireEvent.click(screen.getByRole("button", { name: "Send report" }));
    expect(await screen.findByText(/We have received your report/)).toBeTruthy();
    expect(api.submitNewsComplaint).toHaveBeenCalledWith(expect.objectContaining({ name: "Pat", claim: "copyright", article: "https://site.example/news/bridge-vote" }));
  });

  it("shows the server's problem and keeps what was typed", async () => {
    api.submitNewsComplaint.mockRejectedValue(err({ email: ["Enter a valid email address."] }));
    renderAt("/news/report");
    await fill();
    fireEvent.click(screen.getByRole("button", { name: "Send report" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Enter a valid email address.");
    expect(screen.getByLabelText("Your name").value).toBe("Pat");
  });
});