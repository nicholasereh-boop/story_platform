import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../features/news/api/newsroom", () => ({
  listNewsroom: vi.fn(), listTakedowns: vi.fn(), takedownAction: vi.fn(), getMonitoring: vi.fn(), listCommentsAdmin: vi.fn(), commentAction: vi.fn(),
}));
import * as api from "../features/news/api/newsroom";
import NewsroomPage from "../features/news/pages/NewsroomPage";
import CommentsPage from "../features/news/pages/CommentsPage";
import TakedownsPage from "../features/news/pages/TakedownsPage";

const paged = (items) => ({ items, pagination: { count: items.length, page: 1, page_size: 20, total_pages: 1, has_next: false, has_previous: false } });
const wrap = (ui) => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter>{ui}</MemoryRouter></QueryClientProvider>);
const complaint = (o = {}) => ({ id: 7, status: "open", claim: "copyright", created_at: "2026-11-03T09:00:00Z", contact_name: "Pat", contact_email: "pat@example.com", message: "That is my article.", article: { id: 3, title: "Council approves new bridge", status: "published" }, article_ref: "", resolution_note: "", ...o });

const healthy = { articles: { published: 4, pending: 2, scheduled: 1 }, open_complaints: 0, pending_comments: 0, alerts: [] };
beforeEach(() => { vi.clearAllMocks(); api.getMonitoring.mockResolvedValue(healthy); });

describe("Newsroom queue", () => {
  it("opens on the pending tab and asks the server for pending articles", async () => {
    api.listNewsroom.mockResolvedValue(paged([{ id: 3, title: "Council approves new bridge", status: "pending", article_type: "licensed", source: { name: "Daily Example" }, updated_at: "2026-11-03T09:00:00Z" }]));
    wrap(<NewsroomPage />);
    expect(await screen.findByText("Council approves new bridge")).toBeTruthy();
    expect(api.listNewsroom).toHaveBeenCalledWith(expect.objectContaining({ status: "pending", page: 1 }));
  });
});

describe("Takedown queue", () => {
  it("lists complaints and shows who sent them and which article they name", async () => {
    api.listTakedowns.mockResolvedValue(paged([complaint()]));
    wrap(<TakedownsPage />);
    expect(await screen.findByText("That is my article.")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Council approves new bridge" }).getAttribute("href")).toBe("/admin/news/articles/3");
    expect(api.listTakedowns).toHaveBeenCalledWith(expect.objectContaining({ status: "open" }));
  });

  it("sends a decision together with the note", async () => {
    api.listTakedowns.mockResolvedValue(paged([complaint()]));
    api.takedownAction.mockResolvedValue({});
    wrap(<TakedownsPage />);
    fireEvent.change(await screen.findByLabelText("Resolution note"), { target: { value: "Checked with the source." } });
    fireEvent.click(screen.getByRole("button", { name: /Uphold/ }));
    await waitFor(() => expect(api.takedownAction).toHaveBeenCalledWith(7, "uphold", { note: "Checked with the source." }));
  });

  it("shows closed complaints without decision buttons", async () => {
    api.listTakedowns.mockResolvedValue(paged([complaint({ status: "upheld", resolution_note: "Withdrawn." })]));
    wrap(<TakedownsPage />);
    expect(await screen.findByText(/Resolution: Withdrawn\./)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Uphold/ })).toBeNull();
  });

  it("shows the server's reason when a decision fails", async () => {
    api.listTakedowns.mockResolvedValue(paged([complaint()]));
    api.takedownAction.mockRejectedValue(Object.assign(new Error("x"), { fieldErrors: { detail: ["Already decided."] } }));
    wrap(<TakedownsPage />);
    fireEvent.click(await screen.findByRole("button", { name: /^Dismiss \(/ }));
    expect(await screen.findByText("Already decided.")).toBeTruthy();
  });
});

describe("Newsroom health strip", () => {
  beforeEach(() => api.listNewsroom.mockResolvedValue(paged([])));

  it("is calm when nothing is wrong", async () => {
    wrap(<NewsroomPage />);
    expect(await screen.findByText("Everything looks healthy.")).toBeTruthy();
    expect(screen.getByText(/4 live · 2 waiting for review/)).toBeTruthy();
  });

  it("shows every problem in plain words", async () => {
    api.getMonitoring.mockResolvedValue({ ...healthy, alerts: [{ level: "error", code: "scheduled_overdue", message: "2 scheduled article(s) are overdue." }, { level: "warning", code: "quarantined", message: "1 article(s) are quarantined and need an editor." }] });
    wrap(<NewsroomPage />);
    expect(await screen.findByText("2 scheduled article(s) are overdue.")).toBeTruthy();
    expect(screen.getByText("1 article(s) are quarantined and need an editor.")).toBeTruthy();
  });

  it("never blocks the newsroom when the health check fails", async () => {
    api.getMonitoring.mockRejectedValue(new Error("down"));
    wrap(<NewsroomPage />);
    expect(await screen.findByText("No articles here.")).toBeTruthy();
    expect(screen.queryByLabelText("Newsroom health")).toBeNull();
  });
});

describe("Comment moderation", () => {
  const row = (o = {}) => ({ id: 5, author: "reader1", email: "reader1@example.com", body: "<b>not bold</b>", status: "pending", created_at: "2026-11-03T09:00:00Z", article: { id: 3, title: "Council approves new bridge", slug: "bridge-vote" }, ...o });

  it("lists comments as plain text with the commenter's email, for staff", async () => {
    api.listCommentsAdmin.mockResolvedValue(paged([row()]));
    wrap(<CommentsPage />);
    expect(await screen.findByText("<b>not bold</b>")).toBeTruthy();
    expect(screen.getByText(/reader1@example.com/)).toBeTruthy();
    expect(api.listCommentsAdmin).toHaveBeenCalledWith(expect.objectContaining({ status: "pending" }));
  });

  it("approves a waiting comment, and offers no approve button for an approved one", async () => {
    api.listCommentsAdmin.mockResolvedValue(paged([row()]));
    api.commentAction.mockResolvedValue({});
    wrap(<CommentsPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Approve" }));
    await waitFor(() => expect(api.commentAction).toHaveBeenCalledWith(5, "approve"));
  });

  it("hides the approve button once a comment is approved", async () => {
    api.listCommentsAdmin.mockResolvedValue(paged([row({ status: "approved" })]));
    wrap(<CommentsPage />);
    await screen.findByText("<b>not bold</b>");
    expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
    expect(screen.getByRole("button", { name: "Hide" })).toBeTruthy();
  });

  it("shows the server's reason when an action fails", async () => {
    api.listCommentsAdmin.mockResolvedValue(paged([row()]));
    api.commentAction.mockRejectedValue(Object.assign(new Error("x"), { fieldErrors: { detail: ["Unknown action."] } }));
    wrap(<CommentsPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Hide" }));
    expect(await screen.findByText("Unknown action.")).toBeTruthy();
  });
});