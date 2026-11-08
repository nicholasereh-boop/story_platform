import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../features/news/api/news", () => ({ listNewsComments: vi.fn(), postNewsComment: vi.fn(), deleteNewsComment: vi.fn() }));
vi.mock("../auth/AuthContext", () => ({ useAuth: vi.fn() }));
import { useAuth } from "../auth/AuthContext";
import * as api from "../features/news/api/news";
import NewsComments from "../features/news/components/NewsComments";

const page = (items) => ({ items, pagination: { count: items.length, page: 1, page_size: 20, total_pages: 1, has_next: false, has_previous: false } });
const comment = (o = {}) => ({ id: 1, author: "reader1", body: "Good reporting", status: "approved", is_mine: false, can_delete: false, created_at: "2026-11-03T09:00:00Z", ...o });
const wrap = () => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter><NewsComments slug="bridge-vote" /></MemoryRouter></QueryClientProvider>);

beforeEach(() => {
  vi.clearAllMocks();
  useAuth.mockReturnValue({ ready: true, user: null });
  api.listNewsComments.mockResolvedValue(page([comment()]));
});

describe("News comments", () => {
  it("lets visitors read, and asks them to log in to write", async () => {
    wrap();
    expect(await screen.findByText("Good reporting")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Log in to comment" }).getAttribute("href")).toBe("/login");
    expect(screen.queryByRole("textbox")).toBeNull();
  });

  it("shows comment text as text, never as markup", async () => {
    api.listNewsComments.mockResolvedValue(page([comment({ body: "<img src=x onerror=alert(1)><b>bold</b>" })]));
    const { container } = wrap();
    expect(await screen.findByText("<img src=x onerror=alert(1)><b>bold</b>")).toBeTruthy();
    expect(container.querySelector("img,b")).toBeNull();
  });

  it("says so when there are no comments yet", async () => {
    api.listNewsComments.mockResolvedValue(page([]));
    wrap();
    expect(await screen.findByText("No comments yet.")).toBeTruthy();
  });

  it("a logged-in reader can post, and is told when moderation holds the comment", async () => {
    useAuth.mockReturnValue({ ready: true, user: { id: 9 } });
    api.postNewsComment.mockResolvedValue(comment({ id: 2, status: "pending", is_mine: true }));
    wrap();
    fireEvent.change(await screen.findByRole("textbox"), { target: { value: "My view" } });
    fireEvent.click(screen.getByRole("button", { name: "Post comment" }));
    await waitFor(() => expect(api.postNewsComment).toHaveBeenCalledWith("bridge-vote", "My view"));
    expect(await screen.findByText(/waiting for approval/)).toBeTruthy();
  });

  it("shows why a comment was refused", async () => {
    useAuth.mockReturnValue({ ready: true, user: { id: 9 } });
    api.postNewsComment.mockRejectedValue(Object.assign(new Error("x"), { status: 429 }));
    wrap();
    fireEvent.change(await screen.findByRole("textbox"), { target: { value: "Again" } });
    fireEvent.click(screen.getByRole("button", { name: "Post comment" }));
    expect(await screen.findByText(/too often/)).toBeTruthy();
  });

  it("deleting your own comment takes two clicks", async () => {
    useAuth.mockReturnValue({ ready: true, user: { id: 9 } });
    api.listNewsComments.mockResolvedValue(page([comment({ is_mine: true, can_delete: true })]));
    api.deleteNewsComment.mockResolvedValue({});
    wrap();
    fireEvent.click(await screen.findByRole("button", { name: "Delete" }));
    expect(api.deleteNewsComment).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Yes, delete" }));
    await waitFor(() => expect(api.deleteNewsComment).toHaveBeenCalledWith(1));
  });

  it("offers no delete button on other readers' comments", async () => {
    useAuth.mockReturnValue({ ready: true, user: { id: 9 } });
    wrap();
    await screen.findByText("Good reporting");
    expect(screen.queryByRole("button", { name: "Delete" })).toBeNull();
  });
});