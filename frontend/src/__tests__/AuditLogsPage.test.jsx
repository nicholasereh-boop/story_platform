import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

vi.mock("../api/security", () => ({ listAuditLogs: vi.fn() }));
import { listAuditLogs } from "../api/security";
import AuditLogsPage from "../pages/admin/AuditLogsPage";

const entry = (id, over = {}) => ({
  id, created_at: "2026-10-01T09:30:00Z", actor: 1, actor_label: "Boss", action: "user.update", action_label: "User account changed (active / staff)",
  object_type: "user", object_id: "7", metadata: { changes: { is_active: [true, false] } }, ip_ref: "abcdef012345", ...over,
});
const page = (items, extra = {}) => ({ items, pagination: { count: items.length, page: 1, page_size: 12, total_pages: 1, has_next: false, has_previous: false, ...extra } });
const show = () => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })}><AuditLogsPage /></QueryClientProvider>);

beforeEach(() => { vi.clearAllMocks(); listAuditLogs.mockResolvedValue(page([entry(1), entry(2, { actor_label: "Deleted user", action: "story.delete", action_label: "Story deleted", object_type: "story", object_id: "4", metadata: {} })])); });

describe("AuditLogsPage", () => {
  it("shows who, what, object and readable details, and is read-only", async () => {
    show();
    const row = within((await screen.findByText("User account changed (active / staff)")).closest("tr"));
    expect(row.getByText("Boss")).toBeTruthy();
    expect(row.getByText("user #7")).toBeTruthy();
    expect(row.getByText("is_active: yes → no")).toBeTruthy();
    expect(screen.getByText("Deleted user")).toBeTruthy();
    // no way to change or delete an entry from this screen
    expect(screen.queryByRole("button", { name: /delete|edit|remove/i })).toBeNull();
  });

  it("renders hostile text from metadata as plain text, never as markup", async () => {
    listAuditLogs.mockResolvedValue(page([entry(1, { metadata: { title: "<img src=x onerror=alert(1)>" } })]));
    const { container } = show();
    expect(await screen.findByText("<img src=x onerror=alert(1)>")).toBeTruthy();
    expect(container.querySelector("img")).toBeNull();
  });

  it("applies the filters it was given and clears them", async () => {
    show();
    await screen.findByText("Boss");
    fireEvent.change(screen.getByLabelText("Action"), { target: { value: "story.*" } });
    fireEvent.change(screen.getByLabelText("Object type"), { target: { value: "story" } });
    fireEvent.change(screen.getByLabelText("Actor (user id)"), { target: { value: "3" } });
    fireEvent.change(screen.getByLabelText("From"), { target: { value: "2026-09-01" } });
    fireEvent.change(screen.getByLabelText("To"), { target: { value: "2026-09-30" } });
    fireEvent.change(screen.getByLabelText("Search"), { target: { value: "launch" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    await waitFor(() => expect(listAuditLogs).toHaveBeenCalledWith({ action: "story.*", object_type: "story", actor: "3", from: "2026-09-01", to: "2026-09-30", q: "launch" }));
    fireEvent.click(screen.getByRole("button", { name: "Clear" }));
    await waitFor(() => expect(listAuditLogs).toHaveBeenLastCalledWith({}));
  });

  it("pages through results", async () => {
    listAuditLogs.mockResolvedValue(page([entry(1)], { total_pages: 3, has_next: true }));
    show();
    await screen.findByText("Boss");
    fireEvent.click(screen.getByRole("button", { name: /Next/ }));
    await waitFor(() => expect(listAuditLogs).toHaveBeenLastCalledWith({ page: 2 }));
  });

  it("shows empty and error states", async () => {
    listAuditLogs.mockResolvedValue(page([]));
    show();
    expect(await screen.findByText("No entries match these filters.")).toBeTruthy();
  });

  it("shows the server's message when it fails", async () => {
    listAuditLogs.mockRejectedValue(Object.assign(new Error("x"), { friendly: "Two-step verification is required." }));
    show();
    expect((await screen.findByRole("alert")).textContent).toMatch(/Two-step verification is required\./);
  });
});
