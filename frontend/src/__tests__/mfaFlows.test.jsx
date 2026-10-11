import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";

const auth = { user: null, ready: true, refreshUser: vi.fn(), logout: vi.fn() };
vi.mock("../auth/AuthContext", () => ({ useAuth: () => auth }));
vi.mock("../api", () => ({ mfaVerify: vi.fn() }));
vi.mock("../api/security", () => ({ mfaStatus: vi.fn(), mfaSetup: vi.fn(), mfaConfirm: vi.fn(), mfaDisable: vi.fn(), mfaNewRecoveryCodes: vi.fn() }));
vi.mock("../utils/download", () => ({ downloadText: vi.fn(), copyText: vi.fn().mockResolvedValue(true) }));

import * as API from "../api";
import * as sec from "../api/security";
import RequireStaff from "../auth/RequireStaff";
import MfaPanel from "../components/account/MfaPanel";

const client = () => new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } } });
const staff = { email: "s@example.com", is_staff: true };

function guard(user) {
  auth.user = user;
  return render(
    <QueryClientProvider client={client()}>
      <MemoryRouter initialEntries={["/admin"]}>
        <Routes>
          <Route path="/admin" element={<RequireStaff><p>admin area</p></RequireStaff>} />
          <Route path="/account" element={<p>account page</p>} />
          <Route path="/login" element={<p>login page</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  auth.ready = true;
  auth.refreshUser.mockResolvedValue({});
  auth.logout.mockResolvedValue({});
});

describe("admin guard and the step-up screen", () => {
  it("lets staff without two-step verification straight in when it is not required", () => {
    guard({ ...staff, mfa: { enabled: false, required: false, verified: false } });
    expect(screen.getByText("admin area")).toBeTruthy();
  });

  it("sends staff to set up two-step verification when the site requires it", () => {
    guard({ ...staff, mfa: { enabled: false, required: true, verified: false } });
    expect(screen.getByText("account page")).toBeTruthy();
  });

  it("asks for a code when the device exists but this session has not proven it", () => {
    guard({ ...staff, mfa: { enabled: true, required: false, verified: false } });
    expect(screen.getByRole("heading", { name: "Two-step verification" })).toBeTruthy();
    expect(screen.queryByText("admin area")).toBeNull();
  });

  it("verifies the code without spaces, then refreshes the user", async () => {
    API.mfaVerify.mockResolvedValue({});
    guard({ ...staff, mfa: { enabled: true, required: false, verified: false } });
    fireEvent.change(screen.getByLabelText("Code"), { target: { value: "123 456" } });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() => expect(API.mfaVerify).toHaveBeenCalledWith({ code: "123456" }));
    await waitFor(() => expect(auth.refreshUser).toHaveBeenCalled());
  });

  it("can use a recovery code instead", async () => {
    API.mfaVerify.mockResolvedValue({});
    guard({ ...staff, mfa: { enabled: true, required: false, verified: false } });
    fireEvent.click(screen.getByRole("button", { name: "Use a recovery code instead" }));
    fireEvent.change(screen.getByLabelText("Recovery code"), { target: { value: " abcd-efgh " } });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() => expect(API.mfaVerify).toHaveBeenCalledWith({ recovery_code: "abcd-efgh" }));
  });

  it("shows the server message for a wrong code and stays on the prompt", async () => {
    const err = Object.assign(new Error("x"), { friendly: "That code is not right.", fieldErrors: {} });
    API.mfaVerify.mockRejectedValue(err);
    guard({ ...staff, mfa: { enabled: true, required: false, verified: false } });
    fireEvent.change(screen.getByLabelText("Code"), { target: { value: "000000" } });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect((await screen.findByRole("alert")).textContent).toContain("That code is not right.");
    expect(auth.refreshUser).not.toHaveBeenCalled();
  });

  it("lets the person log out from the prompt", async () => {
    guard({ ...staff, mfa: { enabled: true, required: false, verified: false } });
    fireEvent.click(screen.getByRole("button", { name: "Log out" }));
    await waitFor(() => expect(auth.logout).toHaveBeenCalled());
    expect(await screen.findByText("login page")).toBeTruthy();
  });
});

describe("MfaPanel: setup, recovery codes, turning off", () => {
  const show = () => render(<QueryClientProvider client={client()}><MfaPanel /></QueryClientProvider>);

  it("walks through setup and gates the recovery codes behind 'I saved them'", async () => {
    sec.mfaStatus.mockResolvedValue({ enabled: false, required: false, verified: false, recovery_codes_left: 0 });
    sec.mfaSetup.mockResolvedValue({ secret: "JBSWY3DPEHPK3PXP", otpauth_uri: "otpauth://totp/Site:s@example.com?secret=JBSWY3DPEHPK3PXP" });
    sec.mfaConfirm.mockResolvedValue({ recovery_codes: ["aaaa-1111", "bbbb-2222"] });
    show();
    fireEvent.click(await screen.findByRole("button", { name: "Set up two-step verification" }));
    expect((await screen.findByTestId("mfa-secret")).textContent).toBe("JBSWY3DPEHPK3PXP");
    fireEvent.change(screen.getByLabelText("Code"), { target: { value: "654 321" } });
    fireEvent.click(screen.getByRole("button", { name: "Turn on" }));
    await waitFor(() => expect(sec.mfaConfirm).toHaveBeenCalledWith("654321"));
    expect(await screen.findByText("aaaa-1111")).toBeTruthy();
    const done = screen.getByRole("button", { name: "Done" });
    expect(done.disabled).toBe(true);
    fireEvent.click(screen.getByLabelText("I saved these codes somewhere safe"));
    expect(done.disabled).toBe(false);
    sec.mfaStatus.mockResolvedValue({ enabled: true, required: false, verified: true, recovery_codes_left: 2 });
    fireEvent.click(done);
    expect(await screen.findByText(/You have 2 recovery codes left/)).toBeTruthy();
    expect(screen.queryByText("aaaa-1111")).toBeNull(); // never shown again
  });

  it("shows a wrong confirmation code as a field error", async () => {
    sec.mfaStatus.mockResolvedValue({ enabled: false, required: false, verified: false, recovery_codes_left: 0 });
    sec.mfaSetup.mockResolvedValue({ secret: "ABC", otpauth_uri: "otpauth://totp/x" });
    sec.mfaConfirm.mockRejectedValue(Object.assign(new Error("x"), { friendly: "bad", fieldErrors: { code: ["That code is not right."] } }));
    show();
    fireEvent.click(await screen.findByRole("button", { name: "Set up two-step verification" }));
    fireEvent.change(await screen.findByLabelText("Code"), { target: { value: "111111" } });
    fireEvent.click(screen.getByRole("button", { name: "Turn on" }));
    expect((await screen.findByRole("alert")).textContent).toContain("That code is not right.");
  });

  it("explains when the site requires it", async () => {
    sec.mfaStatus.mockResolvedValue({ enabled: false, required: true, verified: false, recovery_codes_left: 0 });
    show();
    expect(await screen.findByText(/required for staff on this site/)).toBeTruthy();
  });

  it("turning off needs the password and a fresh code", async () => {
    sec.mfaStatus.mockResolvedValue({ enabled: true, required: false, verified: true, recovery_codes_left: 8 });
    sec.mfaDisable.mockResolvedValue({});
    show();
    fireEvent.click(await screen.findByRole("button", { name: "Turn off" }));
    const submit = screen.getByRole("button", { name: "Turn off two-step verification" });
    expect(submit.disabled).toBe(true); // no code yet
    fireEvent.change(screen.getByLabelText(/^Password/), { target: { value: "pw-12345" } });
    fireEvent.change(screen.getByLabelText("Code from your authenticator app"), { target: { value: "123 456" } });
    fireEvent.click(submit);
    await waitFor(() => expect(sec.mfaDisable).toHaveBeenCalledWith({ password: "pw-12345", code: "123456" }, expect.anything()));
  });

  it("new recovery codes are shown once after a fresh code", async () => {
    sec.mfaStatus.mockResolvedValue({ enabled: true, required: false, verified: true, recovery_codes_left: 1 });
    sec.mfaNewRecoveryCodes.mockResolvedValue({ recovery_codes: ["new-0001"] });
    show();
    expect(await screen.findByText(/You have 1 recovery code left/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "New recovery codes" }));
    fireEvent.change(screen.getByLabelText("Code from your authenticator app"), { target: { value: "222333" } });
    fireEvent.click(screen.getByRole("button", { name: "Create new codes" }));
    expect(await screen.findByText("new-0001")).toBeTruthy();
  });
});
