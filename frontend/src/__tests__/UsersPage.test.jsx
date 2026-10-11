import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const auth = { user: { id: 1, email: "boss@example.com", is_staff: true, is_superuser: true } };
vi.mock("../auth/AuthContext", () => ({ useAuth: () => auth }));
vi.mock("../api/security", () => ({ listUsers: vi.fn(), patchUser: vi.fn(), revokeUserSessions: vi.fn(), resendUserVerification: vi.fn() }));

import * as sec from "../api/security";
import UsersPage, { actionRules } from "../pages/admin/UsersPage";

const row = (id, over = {}) => ({
  id, email: `u${id}@example.com`, display_name: `User ${id}`, role: "reader", is_active: true, is_staff: false, is_superuser: false, email_verified: true,
  date_joined: "2026-01-02T10:00:00Z", last_login: null, comment_count: 2, like_count: 3, mfa_enabled: false, anonymised: false, ...over,
});
const boss = row(1, { email: "boss@example.com", display_name: "Boss", role: "superuser", is_staff: true, is_superuser: true });
const page = (items, extra = {}) => ({ items, pagination: { count: items.length, page: 1, page_size: 12, total_pages: 1, has_next: false, has_previous: false, ...extra } });

function show() {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })}><UsersPage /></QueryClientProvider>);
}
const rowOf = async (email) => within((await screen.findByText(email)).closest("tr"));

beforeEach(() => {
  vi.clearAllMocks();
  auth.user = { id: 1, email: "boss@example.com", is_staff: true, is_superuser: true };
  sec.listUsers.mockImplementation(async (params) => (params.role === "superuser" ? page([boss, row(9, { role: "superuser", is_superuser: true, is_staff: true })]) : page([boss, row(2), row(3, { email_verified: false })])));
  sec.patchUser.mockResolvedValue({});
  sec.revokeUserSessions.mockResolvedValue({ ended: 1 });
  sec.resendUserVerification.mockResolvedValue({ sent: true });
});

describe("UsersPage", () => {
  it("lists users with role and status badges and activity", async () => {
    show();
    const r2 = await rowOf("u2@example.com");
    expect(r2.getByText("Reader")).toBeTruthy();
    expect(r2.getByText("Active")).toBeTruthy();
    expect(r2.getByText("Verified")).toBeTruthy();
    expect(r2.getByText("2 comments, 3 likes")).toBeTruthy();
    expect((await rowOf("u3@example.com")).getByText("Not verified")).toBeTruthy();
    expect((await rowOf("boss@example.com")).getByText("Superuser")).toBeTruthy();
  });

  it("sends only the filters that have a value, and clears them", async () => {
    show();
    await screen.findByText("u2@example.com");
    fireEvent.change(screen.getByLabelText("Search"), { target: { value: "nia" } });
    fireEvent.change(screen.getByLabelText("Role"), { target: { value: "staff" } });
    fireEvent.change(screen.getByLabelText("Status"), { target: { value: "0" } });
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    await waitFor(() => expect(sec.listUsers).toHaveBeenCalledWith({ q: "nia", role: "staff", active: "0" }));
    fireEvent.click(screen.getByRole("button", { name: "Clear" }));
    await waitFor(() => expect(sec.listUsers).toHaveBeenLastCalledWith({}));
  });

  it("shows loading, empty and error states", async () => {
    sec.listUsers.mockImplementation(async (p) => (p.role ? page([boss]) : page([])));
    show();
    expect(screen.getByText("Loading users…")).toBeTruthy();
    expect(await screen.findByText("No users match these filters.")).toBeTruthy();
  });

  it("shows the server's message when loading fails", async () => {
    sec.listUsers.mockRejectedValue(Object.assign(new Error("x"), { friendly: "Staff access only." }));
    show();
    expect((await screen.findByRole("alert")).textContent).toMatch(/Staff access only\./);
  });

  it("asks before deactivating, then does it", async () => {
    show();
    const r2 = await rowOf("u2@example.com");
    fireEvent.click(r2.getByRole("button", { name: "Deactivate" }));
    const dialog = await screen.findByRole("dialog", { name: "Deactivate this account?" });
    expect(sec.patchUser).not.toHaveBeenCalled(); // nothing happens until confirmed
    fireEvent.click(within(dialog).getByRole("button", { name: "Deactivate" }));
    await waitFor(() => expect(sec.patchUser).toHaveBeenCalledWith(2, { is_active: false }));
    expect(await screen.findByText("u2@example.com was deactivated and signed out.")).toBeTruthy();
  });

  it("cancel does nothing", async () => {
    show();
    fireEvent.click((await rowOf("u2@example.com")).getByRole("button", { name: "Make staff" }));
    fireEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Cancel" }));
    expect(sec.patchUser).not.toHaveBeenCalled();
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("superusers can make staff; revoke sessions and resend verification work", async () => {
    show();
    fireEvent.click((await rowOf("u2@example.com")).getByRole("button", { name: "Make staff" }));
    fireEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Make staff" }));
    await waitFor(() => expect(sec.patchUser).toHaveBeenCalledWith(2, { is_staff: true }));

    fireEvent.click((await rowOf("u2@example.com")).getByRole("button", { name: "Sign out everywhere" }));
    fireEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Sign out" }));
    await waitFor(() => expect(sec.revokeUserSessions).toHaveBeenCalledWith(2));

    fireEvent.click((await rowOf("u3@example.com")).getByRole("button", { name: "Resend verification" }));
    fireEvent.click(within(await screen.findByRole("dialog")).getByRole("button", { name: "Send email" }));
    await waitFor(() => expect(sec.resendUserVerification).toHaveBeenCalledWith(3));
  });

  it("shows the server's error inside the dialog and keeps it open", async () => {
    sec.patchUser.mockRejectedValue(Object.assign(new Error("x"), { friendly: "You cannot deactivate or demote yourself." }));
    show();
    fireEvent.click((await rowOf("u2@example.com")).getByRole("button", { name: "Deactivate" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Deactivate" }));
    expect((await within(dialog).findByRole("alert")).textContent).toBe("You cannot deactivate or demote yourself.");
  });

  it("disables what the rules forbid, with the reason as the tooltip", async () => {
    show();
    const me = await rowOf("boss@example.com");
    const deactivate = me.getByRole("button", { name: /Deactivate/ });
    expect(deactivate.disabled).toBe(true);
    expect(deactivate.title).toBe("You cannot deactivate yourself.");
    expect(me.getByRole("button", { name: /Remove staff/ }).title).toBe("A superuser always has the staff role.");
  });

  it("staff (not superusers) cannot change roles or touch superusers", async () => {
    auth.user = { id: 5, email: "staff@example.com", is_staff: true, is_superuser: false };
    show();
    const r2 = await rowOf("u2@example.com");
    const grant = r2.getByRole("button", { name: /Make staff/ });
    expect(grant.disabled).toBe(true);
    expect(grant.title).toBe("Only a superuser can grant or remove the staff role.");
    expect(r2.getByRole("button", { name: "Deactivate" }).disabled).toBe(false);
    const sup = await rowOf("boss@example.com");
    expect(sup.getByRole("button", { name: /Deactivate/ }).title).toBe("Only a superuser can change a superuser account.");
    expect(sup.getByRole("button", { name: /Sign out everywhere/ }).disabled).toBe(true);
  });

  it("explains why the last active superuser cannot be deactivated", async () => {
    sec.listUsers.mockImplementation(async (p) => (p.role === "superuser" ? page([boss]) : page([boss, row(2)])));
    auth.user = { id: 5, email: "other@example.com", is_staff: true, is_superuser: true };
    show();
    const me = await rowOf("boss@example.com");
    await waitFor(() => expect(me.getByRole("button", { name: /Deactivate/ }).title).toMatch(/only active superuser/));
  });
});

describe("actionRules", () => {
  const base = { me: { id: 1 }, isSuperuser: true, lastSuperuser: false };
  it("allows ordinary actions on a reader", () => {
    const r = actionRules({ ...base, target: row(2) });
    expect(r.toggleActive).toBe("");
    expect(r.toggleStaff).toBe("");
    expect(r.sessions).toBe("");
  });
  it("blocks everything on an account its owner deleted", () => {
    const r = actionRules({ ...base, target: row(2, { anonymised: true }) });
    expect(r.toggleActive).toMatch(/deleted/);
    expect(r.sessions).toMatch(/deleted/);
  });
  it("does not offer verification for deactivated or verified accounts", () => {
    expect(actionRules({ ...base, target: row(2, { is_active: false, email_verified: false }) }).verification).toMatch(/deactivated/);
    expect(actionRules({ ...base, target: row(2) }).verification).toBe("Already verified.");
  });
});
