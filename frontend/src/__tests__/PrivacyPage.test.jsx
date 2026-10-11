import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

vi.mock("../api/security", () => ({ getPrivacyPolicy: vi.fn() }));
import { getPrivacyPolicy } from "../api/security";
import PrivacyPage from "../pages/public/PrivacyPage";
import { ConsentProvider } from "../privacy/ConsentContext";
import { STORAGE_KEYS } from "../privacy/storageKeys";

const policy = (over = {}) => ({
  site_name: "StoryBoard", operator_name: "Example Media Ltd", contact_email: "privacy@example.com", effective_date: "2026-10-01",
  consent_mode: "notice", analytics_enabled: true,
  retention: { analytics_events_days: 60, analytics_visitors_days: 400, audit_log_days: 200, comment_edit_window_minutes: 20 },
  cookies: [
    { name: "sessionid", purpose: "Keeps you logged in.", duration: "14 days (staff: ends after 120 minutes of inactivity)", necessary: true },
    { name: "csrftoken", purpose: "Protects forms.", duration: "365 days", necessary: true },
  ],
  ...over,
});
const show = () => render(
  <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <MemoryRouter><ConsentProvider mode="notice"><PrivacyPage /></ConsentProvider></MemoryRouter>
  </QueryClientProvider>
);
beforeEach(() => vi.clearAllMocks());

describe("PrivacyPage", () => {
  it("prints the names, dates and numbers it gets from the server", async () => {
    getPrivacyPolicy.mockResolvedValue(policy());
    show();
    expect(await screen.findByRole("heading", { name: "Privacy policy" })).toBeTruthy();
    expect(screen.getByText(/Example Media Ltd runs StoryBoard/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "privacy@example.com" }).getAttribute("href")).toBe("mailto:privacy@example.com");
    expect(screen.getByText("Effective date: 2026-10-01")).toBeTruthy();
    expect(screen.getByText(/Individual page views: 60 days/)).toBeTruthy();
    expect(screen.getByText(/Audit log entries: 200 days/)).toBeTruthy();
    expect(screen.getByText(/edit a comment for 20 minutes/)).toBeTruthy();
  });

  it("marks the legal wording as needing the owner's confirmation", async () => {
    getPrivacyPolicy.mockResolvedValue(policy());
    show();
    expect(await screen.findByText(/To be confirmed by the site owner/)).toBeTruthy();
    expect(screen.getByRole("note").textContent).toMatch(/reviewed and confirmed/);
  });

  it("lists every cookie from the server and every browser storage key", async () => {
    getPrivacyPolicy.mockResolvedValue(policy());
    show();
    const cookies = within(await screen.findByRole("table", { name: "Cookies" }));
    expect(cookies.getByText("sessionid")).toBeTruthy();
    expect(cookies.getByText("csrftoken")).toBeTruthy();
    const storage = within(screen.getByRole("table", { name: /Browser storage/ }));
    for (const entry of STORAGE_KEYS) expect(storage.getByText(entry.key)).toBeTruthy();
  });

  it("shows how to exercise the rights, and a missing date or contact is said plainly", async () => {
    getPrivacyPolicy.mockResolvedValue(policy({ effective_date: "", contact_email: "" }));
    show();
    expect(await screen.findByText(/not yet set by the site owner/)).toBeTruthy();
    expect(screen.getByText(/has not published a contact address/)).toBeTruthy();
    expect(screen.getAllByRole("link", { name: /download your data|delete your account/i }).length).toBe(2);
  });

  it("says visit counting is off when the site has switched analytics off", async () => {
    getPrivacyPolicy.mockResolvedValue(policy({ analytics_enabled: false }));
    show();
    expect(await screen.findByText(/is switched off on this site/)).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Your choice about visit counting" })).toBeNull();
  });

  it("explains an opt-in site differently", async () => {
    getPrivacyPolicy.mockResolvedValue(policy({ consent_mode: "opt_in" }));
    show();
    expect(await screen.findByText(/Counting stays off until you accept/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Change my privacy choice" })).toBeTruthy();
  });

  it("shows an error with a retry when the policy cannot be loaded", async () => {
    getPrivacyPolicy.mockRejectedValue(Object.assign(new Error("x"), { friendly: "Cannot reach the server." }));
    show();
    expect((await screen.findByRole("alert")).textContent).toMatch(/Cannot reach the server/);
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });
});
