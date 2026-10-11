import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("../auth/AuthContext", () => ({ useAuth: () => ({ isStaff: false }) }));

import ConsentBanner from "../components/public/ConsentBanner";
import Footer from "../components/public/Footer";
import { CONSENT_KEY, clearConsent } from "../privacy/consent";
import { ConsentProvider } from "../privacy/ConsentContext";

function show(mode, at = "/") {
  return render(
    <MemoryRouter initialEntries={[at]}>
      <ConsentProvider mode={mode}>
        <Footer />
        <ConsentBanner />
      </ConsentProvider>
    </MemoryRouter>
  );
}
const stored = () => JSON.parse(window.localStorage.getItem(CONSENT_KEY) || "null");

beforeEach(() => { window.localStorage.clear(); clearConsent(); });

describe("consent banner", () => {
  it("is not shown in notice mode, where the footer keeps the opt-out switch", () => {
    show("notice");
    expect(screen.queryByRole("region", { name: "Your privacy choice" })).toBeNull();
    expect(screen.getByRole("button", { name: /Analytics: on/ })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Privacy settings" })).toBeNull();
  });

  it.each(["opt_in", "opt_out"])("asks in %s mode with equally prominent Accept and Reject and a policy link", (mode) => {
    show(mode);
    const banner = screen.getByRole("region", { name: "Your privacy choice" });
    const accept = screen.getByRole("button", { name: "Accept" });
    const reject = screen.getByRole("button", { name: "Reject" });
    expect(accept.className).toBe(reject.className); // same style: neither is nudged
    expect(banner.querySelector('a[href="/privacy"]')).toBeTruthy();
    expect(screen.queryByRole("dialog")).toBeNull(); // not a modal: nothing traps focus
  });

  it("remembers Accept, hides, and can be reopened from the footer", () => {
    show("opt_in");
    fireEvent.click(screen.getByRole("button", { name: "Accept" }));
    expect(stored().choice).toBe("accepted");
    expect(screen.queryByRole("region", { name: "Your privacy choice" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Privacy settings" }));
    expect(screen.getByRole("region", { name: "Your privacy choice" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Reject" }));
    expect(stored().choice).toBe("rejected");
  });

  it("does not ask again once a choice is remembered", () => {
    window.localStorage.setItem(CONSENT_KEY, JSON.stringify({ choice: "rejected", at: Date.now() }));
    show("opt_out");
    expect(screen.queryByRole("region", { name: "Your privacy choice" })).toBeNull();
  });

  it("asks again after six months", () => {
    window.localStorage.setItem(CONSENT_KEY, JSON.stringify({ choice: "accepted", at: Date.now() - 181 * 24 * 3600 * 1000 }));
    show("opt_in");
    expect(screen.getByRole("region", { name: "Your privacy choice" })).toBeTruthy();
  });

  it.each(["/admin/stories", "/login", "/register", "/forgot-password", "/reset-password", "/verify-email", "/account"])("never appears on %s", (path) => {
    show("opt_in", path);
    expect(screen.queryByRole("region", { name: "Your privacy choice" })).toBeNull();
  });

  it("still works when the browser blocks storage", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("blocked"); });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("blocked"); });
    show("opt_out");
    fireEvent.click(screen.getByRole("button", { name: "Reject" }));
    expect(screen.queryByRole("region", { name: "Your privacy choice" })).toBeNull();
    vi.restoreAllMocks();
  });
});
