import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import StoryCard from "../components/public/StoryCard";

const story = (extra = {}) => ({
  id: 1, title: "A lighthouse story", slug: "a-lighthouse-story", excerpt: "Short excerpt.",
  cover: { url: "/media/a.jpg", alt_text: "Lighthouse", width: 800, height: 450 },
  categories: [{ name: "News", slug: "news" }], tags: [], author: "Nia", published_at: "2026-03-05T10:00:00Z", reading_minutes: 4, is_featured: false,
  ...extra,
});
const show = (s, props) => render(<MemoryRouter><StoryCard story={s} {...props} /></MemoryRouter>);

describe("StoryCard", () => {
  it("shows title link, category, excerpt and meta", () => {
    show(story());
    expect(screen.getByRole("link", { name: "A lighthouse story" }).getAttribute("href")).toBe("/stories/a-lighthouse-story");
    expect(screen.getByRole("link", { name: "News" }).getAttribute("href")).toBe("/categories/news");
    expect(screen.getByText("Short excerpt.")).toBeTruthy();
    expect(screen.getByText(/Nia · .* · 4 min read/)).toBeTruthy();
  });

  it("uses a lazy cover with its size to avoid layout shift", () => {
    const { container } = show(story());
    const img = container.querySelector("img");
    expect(img.getAttribute("loading")).toBe("lazy");
    expect(img.getAttribute("width")).toBe("800");
    expect(img.getAttribute("height")).toBe("450");
  });

  it("works without a cover (placeholder, no broken image)", () => {
    const { container } = show(story({ cover: null }));
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector(".card-placeholder")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "A lighthouse story" })).toBeTruthy();
  });

  it("works with no category, no excerpt and no author", () => {
    show(story({ categories: [], excerpt: "", author: null }));
    expect(screen.queryByRole("link", { name: "News" })).toBeNull();
    expect(screen.getByRole("heading", { name: "A lighthouse story" })).toBeTruthy();
  });

  it("renders a very long title in full (CSS clamps it) without breaking", () => {
    const title = `Long ${"title ".repeat(60)}`.trim();
    show(story({ title }));
    expect(screen.getByRole("heading").textContent).toBe(title);
  });

  it("renders text from the API as text, not HTML", () => {
    const { container } = show(story({ title: '<img src=x onerror="alert(1)">' }));
    expect(container.querySelectorAll("img")).toHaveLength(1); // only the cover
    expect(screen.getByRole("heading").textContent).toBe('<img src=x onerror="alert(1)">');
  });

  it("uses the requested heading level", () => {
    show(story(), { headingLevel: 2 });
    expect(screen.getByRole("heading", { level: 2 })).toBeTruthy();
  });
});
