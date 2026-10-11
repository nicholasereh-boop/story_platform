import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, useNavigate } from "react-router-dom";

const auth = { user: null, ready: true };
vi.mock("../auth/AuthContext", () => ({ useAuth: () => auth }));
vi.mock("../api", () => ({ providers: vi.fn() }));

import * as api from "../api";
import { SignupPromptProvider, useSignupPrompt } from "../engagement/SignupPromptContext";
import { DISMISS_DAYS, DISMISS_KEY, dismiss, isBlockedPath, isDismissed, recordPageView, resetMemoryViews } from "../engagement/signupPrompt";

const DAY = 24 * 60 * 60 * 1000;

function Probe({ reason, label }) {
  const { request } = useSignupPrompt();
  return <button type="button" onClick={() => request(reason)}>{label || reason}</button>;
}
function Nav() {
  const navigate = useNavigate();
  return ["/a", "/b", "/c", "/d", "/login"].map((to) => <button key={to} type="button" onClick={() => navigate(to)}>go {to}</button>);
}
function show(path = "/stories/x", children = <Probe reason="read" />, props = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <SignupPromptProvider {...props}>{children}</SignupPromptProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
}
const dialog = () => screen.queryByRole("dialog");
const click = (name) => fireEvent.click(screen.getByRole("button", { name }));

beforeEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  resetMemoryViews();
  auth.user = null;
  auth.ready = true;
  api.providers.mockResolvedValue({ google: false }); // Google sign-in is not configured
});
afterEach(() => vi.restoreAllMocks());

describe("signup prompt rules (pure functions)", () => {
  it("is quiet for 14 days after a dismissal and speaks up again when the flag expires", () => {
    const now = 1_000_000;
    expect(isDismissed(now)).toBe(false);
    expect(dismiss(now)).toBe(true);
    expect(isDismissed(now + 1)).toBe(true);
    expect(isDismissed(now + DISMISS_DAYS * DAY - 1)).toBe(true);
    expect(isDismissed(now + DISMISS_DAYS * DAY + 1)).toBe(false);
    expect(window.localStorage.getItem(DISMISS_KEY)).toBeNull(); // the expired flag is cleaned up
  });

  it("treats a garbage flag as not dismissed", () => {
    window.localStorage.setItem(DISMISS_KEY, "not-a-number");
    expect(isDismissed()).toBe(false);
  });

  it("never allows the prompt on auth pages or the admin", () => {
    for (const path of ["/login", "/register", "/forgot-password", "/reset-password", "/verify-email", "/admin", "/admin/comments"]) {
      expect(isBlockedPath(path), path).toBe(true);
    }
    for (const path of ["/", "/stories/login-tips", "/account", "/administration"]) expect(isBlockedPath(path), path).toBe(false);
  });

  it("counts page views per session", () => {
    expect([recordPageView(), recordPageView(), recordPageView()]).toEqual([1, 2, 3]);
  });

  it("does not throw when storage is unavailable", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("denied"); });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("denied"); });
    expect(isDismissed()).toBe(false);
    expect(dismiss()).toBe(false);
    expect([recordPageView(), recordPageView()]).toEqual([1, 2]); // in-memory fallback
  });
});

describe("SignupPromptProvider", () => {
  it("shows the prompt with Google-less sign-up and log-in links and a Close button", () => {
    show();
    click("read");
    expect(dialog()).toBeTruthy();
    expect(screen.getByRole("link", { name: "Sign up with email" }).getAttribute("href")).toBe("/register");
    expect(screen.getByRole("link", { name: "Log in" }).getAttribute("href")).toBe("/login");
    expect(screen.getByRole("button", { name: "Close" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /google/i })).toBeNull(); // backend says Google is not configured
  });

  it("is not shown twice inside the dismissal window, but an explicit Like or Comment click still opens it", () => {
    show("/stories/x", <><Probe reason="read" /><Probe reason="like" /><Probe reason="comment" /></>);
    click("read");
    click("Close");
    expect(dialog()).toBeNull();
    expect(window.localStorage.getItem(DISMISS_KEY)).not.toBeNull();

    click("read"); // automatic trigger: refused
    expect(dialog()).toBeNull();

    click("like"); // explicit click: allowed
    expect(dialog()).toBeTruthy();
    click("Close");
    click("comment");
    expect(dialog()).toBeTruthy();
  });

  it("shows an automatic prompt only once per page session even without a dismissal flag", () => {
    show();
    click("read");
    fireEvent.keyDown(document, { key: "Escape" }); // Esc closes
    expect(dialog()).toBeNull();
    window.localStorage.clear();
    click("read");
    expect(dialog()).toBeNull();
  });

  it("speaks up again once the 14 days are over", () => {
    window.localStorage.setItem(DISMISS_KEY, String(Date.now() - 1000));
    show();
    click("read");
    expect(dialog()).toBeTruthy();
  });

  it("stays quiet inside the window", () => {
    window.localStorage.setItem(DISMISS_KEY, String(Date.now() + DAY));
    show();
    click("read");
    expect(dialog()).toBeNull();
  });

  it("never opens on auth pages or the admin, not even for an explicit click", () => {
    for (const path of ["/login", "/register", "/forgot-password", "/reset-password", "/verify-email", "/admin/comments"]) {
      const { unmount } = show(path, <><Probe reason="read" /><Probe reason="like" /></>);
      click("read");
      click("like");
      expect(dialog(), path).toBeNull();
      unmount();
    }
  });

  it("never opens for a logged-in user", () => {
    auth.user = { email: "a@example.com" };
    show("/stories/x", <><Probe reason="read" /><Probe reason="like" /></>);
    click("read");
    click("like");
    expect(dialog()).toBeNull();
  });

  it("does not crash when storage fails: it opens, closes, and stays quiet for the rest of the page session", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("denied"); });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("denied"); });
    vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => { throw new Error("denied"); });
    show();
    click("read");
    expect(dialog()).toBeTruthy();
    click("Close");
    expect(dialog()).toBeNull();
    click("read");
    expect(dialog()).toBeNull();
  });

  it("appears on the 3rd page view of a session, only then, and login pages do not count", async () => {
    show("/a", <Nav />, { pageViewDelayMs: 0 });
    click("go /login"); // not counted, never shows
    click("go /b");
    expect(dialog()).toBeNull();
    click("go /c"); // views: /a, /b, /c = 3
    expect(await screen.findByRole("dialog")).toBeTruthy();
    click("Close");
    click("go /d"); // the 4th view never prompts
    await act(async () => { await new Promise((r) => setTimeout(r, 20)); });
    expect(dialog()).toBeNull();
  });

  it("does not prompt on the 3rd view when that page is an auth page", async () => {
    show("/a", <Nav />, { pageViewDelayMs: 0 });
    click("go /b");
    click("go /login");
    await act(async () => { await new Promise((r) => setTimeout(r, 20)); });
    expect(dialog()).toBeNull();
  });
});
