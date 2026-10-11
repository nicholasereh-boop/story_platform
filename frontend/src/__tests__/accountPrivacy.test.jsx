import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";

const auth = { user: { id: 5, email: "me@example.com", mfa: { enabled: false } }, logout: vi.fn() };
vi.mock("../auth/AuthContext", () => ({ useAuth: () => auth }));
vi.mock("../api/security", () => ({ listMySessions: vi.fn(), revokeAllSessions: vi.fn(), exportMyData: vi.fn(), deleteMyAccount: vi.fn() }));
vi.mock("../utils/download", () => ({ downloadText: vi.fn(), copyText: vi.fn() }));

import * as sec from "../api/security";
import { downloadText } from "../utils/download";
import DataPanel from "../components/account/DataPanel";
import SessionsPanel from "../components/account/SessionsPanel";

function show(element) {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } })}>
      <MemoryRouter initialEntries={["/account"]}>
        <Routes>
          <Route path="/account" element={element} />
          <Route path="/login" element={<p>login page</p>} />
          <Route path="/" element={<p>home page</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  auth.user = { id: 5, email: "me@example.com", mfa: { enabled: false } };
  auth.logout.mockResolvedValue({});
});

describe("SessionsPanel", () => {
  const sessions = [
    { id: "a", device: "Firefox on Windows", current: true, created_at: "2026-10-01T10:00:00Z", last_seen_at: "2026-10-02T10:00:00Z" },
    { id: "b", device: "Safari on iPhone", current: false, created_at: "2026-09-20T10:00:00Z", last_seen_at: "2026-09-21T10:00:00Z" },
  ];

  it("lists devices and marks this one, with no IP or browser string", async () => {
    sec.listMySessions.mockResolvedValue(sessions);
    show(<SessionsPanel />);
    expect(await screen.findByText("Firefox on Windows")).toBeTruthy();
    expect(screen.getAllByText("This device")).toHaveLength(1);
    expect(screen.getByText("Safari on iPhone")).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b|Mozilla/);
  });

  it("shows an error when the list cannot load", async () => {
    sec.listMySessions.mockRejectedValue(Object.assign(new Error("x"), { friendly: "Could not load sessions." }));
    show(<SessionsPanel />);
    expect((await screen.findByRole("alert")).textContent).toContain("Could not load sessions.");
  });

  it("asks before signing out everywhere, then logs out and goes to login", async () => {
    sec.listMySessions.mockResolvedValue(sessions);
    sec.revokeAllSessions.mockResolvedValue({ ended: 2 });
    show(<SessionsPanel />);
    await screen.findByText("Firefox on Windows");
    fireEvent.click(screen.getByRole("button", { name: "Sign out of all devices" }));
    expect(sec.revokeAllSessions).not.toHaveBeenCalled(); // the dialog comes first
    const dialog = screen.getByRole("dialog");
    fireEvent.click(Array.from(dialog.querySelectorAll("button")).find((b) => b.textContent === "Sign out of all devices"));
    await waitFor(() => expect(sec.revokeAllSessions).toHaveBeenCalled());
    expect(await screen.findByText("login page")).toBeTruthy();
  });

  it("cancel leaves everything alone", async () => {
    sec.listMySessions.mockResolvedValue(sessions);
    show(<SessionsPanel />);
    await screen.findByText("Firefox on Windows");
    fireEvent.click(screen.getByRole("button", { name: "Sign out of all devices" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(sec.revokeAllSessions).not.toHaveBeenCalled();
  });

  it("keeps the dialog and shows the error when revoking fails", async () => {
    sec.listMySessions.mockResolvedValue(sessions);
    sec.revokeAllSessions.mockRejectedValue(Object.assign(new Error("x"), { friendly: "Try again later." }));
    show(<SessionsPanel />);
    await screen.findByText("Firefox on Windows");
    fireEvent.click(screen.getByRole("button", { name: "Sign out of all devices" }));
    const dialog = screen.getByRole("dialog");
    fireEvent.click(Array.from(dialog.querySelectorAll("button")).find((b) => b.textContent === "Sign out of all devices"));
    expect((await screen.findByRole("alert")).textContent).toContain("Try again later.");
    expect(auth.logout).not.toHaveBeenCalled();
  });
});

describe("DataPanel: export and account deletion", () => {
  it("downloads my data as a JSON file", async () => {
    sec.exportMyData.mockResolvedValue({ profile: { display_name: "Me" }, comments: [] });
    show(<DataPanel />);
    fireEvent.click(screen.getByRole("button", { name: "Download my data" }));
    await waitFor(() => expect(downloadText).toHaveBeenCalled());
    const [name, text, type] = downloadText.mock.calls[0];
    expect(name).toBe("my-data.json");
    expect(type).toBe("application/json");
    expect(JSON.parse(text).profile.display_name).toBe("Me");
  });

  it("shows the server message when the export is throttled", async () => {
    sec.exportMyData.mockRejectedValue(Object.assign(new Error("x"), { friendly: "Too many requests. Try again in an hour." }));
    show(<DataPanel />);
    fireEvent.click(screen.getByRole("button", { name: "Download my data" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Too many requests");
    expect(downloadText).not.toHaveBeenCalled();
  });

  const openDialog = () => fireEvent.click(screen.getByRole("button", { name: "Delete my account…" }));

  it("will not delete until a password and the confirmation box are given", async () => {
    show(<DataPanel />);
    openDialog();
    const go = screen.getByRole("button", { name: "Delete my account permanently" });
    expect(go.disabled).toBe(true);
    fireEvent.change(screen.getByLabelText("Your password"), { target: { value: "pw-12345" } });
    expect(go.disabled).toBe(true); // still needs the "I understand" box
    fireEvent.click(screen.getByLabelText(/I understand my account will be deleted/));
    expect(go.disabled).toBe(false);
    expect(sec.deleteMyAccount).not.toHaveBeenCalled();
  });

  it("deletes with the password, logs out and goes home", async () => {
    sec.deleteMyAccount.mockResolvedValue({});
    show(<DataPanel />);
    openDialog();
    fireEvent.change(screen.getByLabelText("Your password"), { target: { value: "pw-12345" } });
    fireEvent.click(screen.getByLabelText(/I understand my account will be deleted/));
    fireEvent.click(screen.getByRole("button", { name: "Delete my account permanently" }));
    await waitFor(() => expect(sec.deleteMyAccount).toHaveBeenCalledWith({ password: "pw-12345" }));
    await waitFor(() => expect(auth.logout).toHaveBeenCalled());
    expect(await screen.findByText("home page")).toBeTruthy();
  });

  it("Google-only accounts confirm by typing their email", async () => {
    sec.deleteMyAccount.mockResolvedValue({});
    show(<DataPanel />);
    openDialog();
    fireEvent.change(screen.getByLabelText(/Or, if you only sign in with Google/), { target: { value: " me@example.com " } });
    fireEvent.click(screen.getByLabelText(/I understand my account will be deleted/));
    fireEvent.click(screen.getByRole("button", { name: "Delete my account permanently" }));
    await waitFor(() => expect(sec.deleteMyAccount).toHaveBeenCalledWith({ email: "me@example.com" }));
  });

  it("asks for an authenticator code when two-step is on", async () => {
    auth.user = { id: 5, email: "me@example.com", mfa: { enabled: true } };
    sec.deleteMyAccount.mockResolvedValue({});
    show(<DataPanel />);
    openDialog();
    fireEvent.change(screen.getByLabelText("Your password"), { target: { value: "pw-12345" } });
    fireEvent.change(screen.getByLabelText("Code from your authenticator app"), { target: { value: "123 456" } });
    fireEvent.click(screen.getByLabelText(/I understand my account will be deleted/));
    fireEvent.click(screen.getByRole("button", { name: "Delete my account permanently" }));
    await waitFor(() => expect(sec.deleteMyAccount).toHaveBeenCalledWith({ password: "pw-12345", code: "123456" }));
  });

  it("keeps the account and shows the problem when the password is wrong", async () => {
    sec.deleteMyAccount.mockRejectedValue(Object.assign(new Error("x"), { friendly: "bad", fieldErrors: { password: ["That password is not right."] } }));
    show(<DataPanel />);
    openDialog();
    fireEvent.change(screen.getByLabelText("Your password"), { target: { value: "nope-12345" } });
    fireEvent.click(screen.getByLabelText(/I understand my account will be deleted/));
    fireEvent.click(screen.getByRole("button", { name: "Delete my account permanently" }));
    expect((await screen.findAllByRole("alert")).map((n) => n.textContent).join(" ")).toContain("That password is not right.");
    expect(auth.logout).not.toHaveBeenCalled();
    expect(screen.queryByText("home page")).toBeNull();
  });
});
