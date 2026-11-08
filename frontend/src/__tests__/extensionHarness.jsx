// Shared setup for the marketplace and video-tools page tests: the REAL routes, the network replaced by mocks.
import { expect, vi } from "vitest";
import { render } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { routes } from "../App";

export const member = { id: 7, email: "ada@example.com", display_name: "Ada", is_staff: false, mfa: { required: false, enabled: false, verified: false } };
export const staff = { ...member, id: 1, is_staff: true };

export function renderAt(path) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } } });
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  const view = render(<QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider>);
  return { ...view, router };
}

export const page = (items) => ({ items, pagination: { count: items.length, page: 1, page_size: 12, total_pages: 1, has_next: false, has_previous: false } });

export const offer = (over = {}) => ({
  package_id: 11, kind: "frontend", version: "1.2.0", size_bytes: 2048, file_count: 12, source: "upload",
  price: "0.00", currency: "USD", is_free: true, ...over,
});

export const card = (over = {}) => ({
  id: 5, slug: "shop-template", title: "Shop Template", summary: "A complete shop.", seller: "Nia", technologies: [{ name: "React", slug: "react" }],
  cover: null, offers: [offer()], has_video: false, currency: "USD", published_at: "2026-10-01T10:00:00Z", ...over,
});

export const detail = (over = {}) => ({
  ...card(), description: "Full description of the shop.", notes: "Run npm install.", youtube_id: "", screenshots: [], status: "published",
  viewer: { is_owner: false, packages: { frontend: { can_download: true, basis: "free", purchased: false } } }, ...over,
});

export function resetBrowser() {
  vi.clearAllMocks();
  window.scrollTo = vi.fn();
  document.head.innerHTML = "";
}

// The project does not install jest-dom, so the few matchers these tests read best with are defined here.
const textOf = (el) => (el?.textContent ?? "").replace(/\s+/g, " ").trim();
expect.extend({
  toBeInTheDocument(el) {
    const pass = Boolean(el) && el.ownerDocument.contains(el);
    return { pass, message: () => `expected element ${pass ? "not " : ""}to be in the document` };
  },
  toHaveAttribute(el, name, value) {
    const actual = el?.getAttribute(name);
    const pass = value === undefined ? actual !== null && actual !== undefined : actual === value;
    return { pass, message: () => `expected attribute ${name} ${pass ? "not " : ""}to be ${JSON.stringify(value)}, got ${JSON.stringify(actual)}` };
  },
  toHaveTextContent(el, expected) {
    const text = textOf(el);
    const pass = expected instanceof RegExp ? expected.test(text) : text.includes(expected);
    return { pass, message: () => `expected text ${JSON.stringify(text)} ${pass ? "not " : ""}to contain ${String(expected)}` };
  },
  toHaveValue(el, expected) {
    return { pass: el?.value === expected, message: () => `expected value ${JSON.stringify(el?.value)} to be ${JSON.stringify(expected)}` };
  },
});
