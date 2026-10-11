import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("../api/engagement", () => ({
  listComments: vi.fn(), createComment: vi.fn(), editComment: vi.fn(), deleteComment: vi.fn(), reportComment: vi.fn(),
}));

import * as api from "../api/engagement";
import CommentList from "../components/engagement/CommentList";

const minutes = (n) => new Date(Date.now() + n * 60_000).toISOString();
const comment = (id, extra = {}) => ({
  id, parent: null, body: `body ${id}`, author: `Author ${id}`, status: "approved", is_mine: false, can_edit: false, can_delete: false,
  edit_expires_at: null, created_at: "2026-03-05T10:00:00Z", edited_at: null, replies: [], ...extra,
});
const page = (items, extra = {}) => ({
  items, pagination: { count: items.length, page: 1, page_size: 20, total_pages: 1, has_next: false, has_previous: false, ...extra },
});
const verified = { email: "me@example.com", email_verified: true };

function show(user = verified) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <CommentList slug="a-story" user={user} />
    </QueryClientProvider>
  );
}
const row = (text) => screen.getByText(text).closest("li");
const has = (el, name) => within(el).queryByRole("button", { name });

beforeEach(() => vi.clearAllMocks());

describe("CommentList states", () => {
  it("shows a loading state", () => {
    api.listComments.mockReturnValue(new Promise(() => {}));
    show();
    expect(screen.getByRole("status", { name: "Loading comments" })).toBeTruthy();
  });

  it("shows an empty state", async () => {
    api.listComments.mockResolvedValue(page([]));
    show();
    expect(await screen.findByText(/no comments yet/i)).toBeTruthy();
  });

  it("shows an error with Try again", async () => {
    api.listComments.mockRejectedValueOnce(Object.assign(new Error("x"), { status: 500, friendly: "Server trouble." }));
    api.listComments.mockResolvedValue(page([comment(1)]));
    show();
    expect((await screen.findByRole("alert")).textContent).toContain("Server trouble.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("body 1")).toBeTruthy();
  });

  it("loads more comments page by page", async () => {
    api.listComments.mockImplementation(async (slug, p) =>
      p === 2 ? { ...page([comment(2)]), pagination: { count: 2, page: 2, page_size: 20, total_pages: 2, has_next: false, has_previous: true } }
        : page([comment(1)], { count: 2, total_pages: 2, has_next: true })
    );
    show();
    await screen.findByText("body 1");
    fireEvent.click(screen.getByRole("button", { name: "Load more comments" }));
    expect(await screen.findByText("body 2")).toBeTruthy();
    expect(api.listComments).toHaveBeenLastCalledWith("a-story", 2);
    expect(screen.queryByRole("button", { name: "Load more comments" })).toBeNull(); // no more pages
  });
});

describe("CommentList content", () => {
  it("renders the body as text, never as HTML", async () => {
    api.listComments.mockResolvedValue(page([comment(1, { body: "<b>bold</b> <img src=x onerror=alert(1)>" })]));
    const { container } = show();
    expect(await screen.findByText("<b>bold</b> <img src=x onerror=alert(1)>")).toBeTruthy();
    expect(container.querySelector("b")).toBeNull();
    expect(container.querySelector("img")).toBeNull();
  });

  it("nests replies one level and gives replies no Reply button", async () => {
    api.listComments.mockResolvedValue(page([comment(1, { replies: [comment(2, { parent: 1 })] })]));
    show();
    await screen.findByText("body 1");
    expect(within(row("body 1")).getByText("body 2")).toBeTruthy();
    expect(has(row("body 2"), "Reply")).toBeNull();
    expect(has(row("body 1"), "Reply")).toBeTruthy();
  });

  it("marks the reader's own pending comment and edited comments", async () => {
    api.listComments.mockResolvedValue(page([comment(1, { status: "pending", is_mine: true }), comment(2, { edited_at: "2026-03-05T10:05:00Z" })]));
    show();
    await screen.findByText("body 1");
    expect(within(row("body 1")).getByText("Pending approval")).toBeTruthy();
    expect(within(row("body 2")).getByText("(edited)")).toBeTruthy();
  });

  it("shows a deleted comment as a placeholder without actions", async () => {
    api.listComments.mockResolvedValue(page([comment(1, { status: "deleted", body: "[This comment was deleted]", author: null, can_delete: true })]));
    show();
    const item = (await screen.findByText("[This comment was deleted]")).closest("li");
    expect(within(item).queryAllByRole("button")).toHaveLength(0);
  });
});

describe("CommentList permissions", () => {
  it("offers Edit and Delete only on the reader's own comments, Report only on other people's", async () => {
    api.listComments.mockResolvedValue(page([
      comment(1, { is_mine: true, can_edit: true, can_delete: true, edit_expires_at: minutes(10) }),
      comment(2),
    ]));
    show();
    await screen.findByText("body 1");
    const mine = row("body 1");
    const theirs = row("body 2");
    expect(has(mine, "Edit")).toBeTruthy();
    expect(has(mine, "Delete")).toBeTruthy();
    expect(has(mine, "Report")).toBeNull();
    expect(has(theirs, "Edit")).toBeNull();
    expect(has(theirs, "Delete")).toBeNull();
    expect(has(theirs, "Report")).toBeTruthy();
  });

  it("hides Edit once the edit window has passed, even if the list is older than that", async () => {
    api.listComments.mockResolvedValue(page([comment(1, { is_mine: true, can_edit: true, can_delete: true, edit_expires_at: minutes(-1) })]));
    show();
    await screen.findByText("body 1");
    expect(has(row("body 1"), "Edit")).toBeNull();
    expect(has(row("body 1"), "Delete")).toBeTruthy(); // deleting is not limited by the window
  });

  it("offers no Reply or Report to a visitor, and no Reply to an unverified reader", async () => {
    api.listComments.mockResolvedValue(page([comment(1)]));
    const first = show(null);
    await screen.findByText("body 1");
    expect(has(row("body 1"), "Reply")).toBeNull();
    expect(has(row("body 1"), "Report")).toBeNull();
    first.unmount();
    show({ email: "u@example.com", email_verified: false });
    await screen.findByText("body 1");
    expect(has(row("body 1"), "Reply")).toBeNull();
    expect(has(row("body 1"), "Report")).toBeTruthy();
  });
});

describe("CommentList actions", () => {
  it("asks for confirmation before deleting", async () => {
    api.listComments.mockResolvedValue(page([comment(7, { is_mine: true, can_delete: true })]));
    api.deleteComment.mockResolvedValue({});
    show();
    await screen.findByText("body 7");
    fireEvent.click(has(row("body 7"), "Delete"));
    const dialog = screen.getByRole("dialog");
    expect(api.deleteComment).not.toHaveBeenCalled();
    fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
    expect(api.deleteComment).not.toHaveBeenCalled();
    fireEvent.click(has(row("body 7"), "Delete"));
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(api.deleteComment).toHaveBeenCalledWith(7));
  });

  it("reports a comment with a reason", async () => {
    api.listComments.mockResolvedValue(page([comment(3)]));
    api.reportComment.mockResolvedValue({ reported: true });
    show();
    await screen.findByText("body 3");
    fireEvent.click(has(row("body 3"), "Report"));
    const dialog = screen.getByRole("dialog");
    fireEvent.change(within(dialog).getByRole("textbox"), { target: { value: "spam" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Send report" }));
    expect(await within(screen.getByRole("dialog")).findByText(/thank you/i)).toBeTruthy();
    expect(api.reportComment).toHaveBeenCalledWith(3, "spam");
  });

  it("posts a reply to the parent comment", async () => {
    api.listComments.mockResolvedValue(page([comment(1)]));
    api.createComment.mockResolvedValue({ id: 9, status: "approved" });
    show();
    await screen.findByText("body 1");
    fireEvent.click(has(row("body 1"), "Reply"));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "Agreed!" } });
    fireEvent.click(screen.getByRole("button", { name: "Post reply" }));
    await waitFor(() => expect(api.createComment).toHaveBeenCalledWith("a-story", "Agreed!", 1));
  });

  it("edits a comment inside the window", async () => {
    api.listComments.mockResolvedValue(page([comment(1, { is_mine: true, can_edit: true, can_delete: true, edit_expires_at: minutes(5) })]));
    api.editComment.mockResolvedValue({});
    show();
    await screen.findByText("body 1");
    fireEvent.click(has(row("body 1"), "Edit"));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "better text" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(api.editComment).toHaveBeenCalledWith(1, "better text"));
  });
});
