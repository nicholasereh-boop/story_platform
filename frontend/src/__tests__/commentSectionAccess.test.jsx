import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

const auth = { user: null, ready: true };
vi.mock("../auth/AuthContext", () => ({ useAuth: () => auth }));
vi.mock("../api/engagement", () => ({ createComment: vi.fn(), listComments: vi.fn().mockResolvedValue({ items: [], pagination: { count: 0, page: 1, page_size: 20, total_pages: 1, has_next: false, has_previous: false } }), editComment: vi.fn(), deleteComment: vi.fn(), reportComment: vi.fn() }));

import CommentSection from "../components/engagement/CommentSection";

function show(props = {}) {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={["/stories/a-story"]}>
        <CommentSection slug="a-story" count={2} {...props} />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  auth.user = null;
  auth.ready = true;
});

describe("who can write a comment", () => {
  it("a visitor cannot: no text box, no Post button, just a clear note with Log in and Create account links", async () => {
    show();
    expect(await screen.findByText(/Only logged-in readers can write comments/)).toBeTruthy();
    expect(screen.getByText(/Reading and liking are open to everyone/)).toBeTruthy();
    expect(screen.queryByRole("textbox")).toBeNull();
    expect(screen.queryByRole("button", { name: /post|comment/i })).toBeNull();
    expect(screen.getByRole("link", { name: "Log in to comment" }).getAttribute("href")).toBe("/login");
    expect(screen.getByRole("link", { name: "Create an account" }).getAttribute("href")).toBe("/register");
  });

  it("a logged-in reader can: the form is there and the note is not", async () => {
    auth.user = { id: 7, email: "a@example.com" };
    show();
    expect(await screen.findByRole("textbox")).toBeTruthy();
    expect(screen.queryByText(/Only logged-in readers can write comments/)).toBeNull();
  });

  it("shows nothing about logging in while the session is still being checked (no flash for logged-in readers)", () => {
    auth.ready = false;
    show();
    expect(screen.queryByText(/Only logged-in readers can write comments/)).toBeNull();
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("everyone sees the comment count in the heading", async () => {
    show();
    expect((await screen.findByRole("heading", { name: /Comments/ })).textContent).toContain("(2)");
  });
});
