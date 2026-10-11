import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

const auth = { user: null, ready: true, register: vi.fn(), resetPassword: vi.fn(), requestPasswordReset: vi.fn(), verifyEmail: vi.fn() };
vi.mock("../auth/AuthContext", () => ({ useAuth: () => auth }));
vi.mock("../api", () => ({ providers: vi.fn() }));

import * as api from "../api";
import ForgotPasswordPage from "../pages/auth/ForgotPasswordPage";
import RegisterPage from "../pages/auth/RegisterPage";
import ResetPasswordPage from "../pages/auth/ResetPasswordPage";
import VerifyEmailPage from "../pages/auth/VerifyEmailPage";

const GOOD = "Correct-horse-battery-9";
const fail = (fieldErrors, friendly = "Please correct the highlighted fields.") => Object.assign(new Error("x"), { status: 400, fieldErrors, friendly });

function show(element, path = "/") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>{element}</MemoryRouter>
    </QueryClientProvider>
  );
}
const typeInto = (label, value) => fireEvent.change(screen.getByLabelText(label), { target: { value } });

beforeEach(() => {
  vi.clearAllMocks();
  auth.user = null;
  auth.ready = true;
  api.providers.mockResolvedValue({ google: false });
});

describe("RegisterPage", () => {
  const fill = (password = GOOD, confirm = password) => {
    typeInto("Email", "new@example.com");
    typeInto("Password", password);
    typeInto("Confirm password", confirm);
    fireEvent.click(screen.getByRole("button", { name: "Sign up" }));
  };

  it("checks the password rules in the browser before calling the server", () => {
    show(<RegisterPage />);
    fill("short");
    expect(screen.getByText("Use at least 10 characters.")).toBeTruthy();
    expect(auth.register).not.toHaveBeenCalled();
  });

  it("catches mismatched passwords and a bad email", () => {
    show(<RegisterPage />);
    typeInto("Email", "nope");
    typeInto("Password", GOOD);
    typeInto("Confirm password", "different-password-1");
    fireEvent.click(screen.getByRole("button", { name: "Sign up" }));
    expect(screen.getByText("Enter a valid email address.")).toBeTruthy();
    expect(screen.getByText("The passwords do not match.")).toBeTruthy();
    expect(auth.register).not.toHaveBeenCalled();
  });

  it("shows the server's field errors next to the fields", async () => {
    auth.register.mockRejectedValue(fail({ email: ["Enter a valid email address."], password: ["This password is too common."] }));
    show(<RegisterPage />);
    fill();
    expect(await screen.findByText("Enter a valid email address.")).toBeTruthy();
    expect(screen.getByText("This password is too common.")).toBeTruthy();
    expect(screen.getByLabelText("Email").getAttribute("aria-invalid")).toBe("true");
  });

  it("shows a general error when the server gives no field errors", async () => {
    auth.register.mockRejectedValue(Object.assign(new Error("x"), { status: 429, fieldErrors: {}, friendly: "Too many sign-ups. Try again later." }));
    show(<RegisterPage />);
    fill();
    expect((await screen.findByRole("alert")).textContent).toBe("Too many sign-ups. Try again later.");
  });

  it("never logs in or reveals whether the address existed: it says to check the email", async () => {
    auth.register.mockResolvedValue({ message: "Check your email." });
    show(<RegisterPage />);
    fill();
    expect(await screen.findByRole("heading", { name: "Check your email" })).toBeTruthy();
    expect(screen.getByText("new@example.com")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Go to log in" })).toBeTruthy();
    expect(auth.register).toHaveBeenCalledWith({ email: "new@example.com", password: GOOD, display_name: "" });
  });

  it("shows the Google button only when the backend says Google is configured", async () => {
    api.providers.mockResolvedValue({ google: true });
    show(<RegisterPage />);
    expect(await screen.findByRole("button", { name: "Sign up with Google" })).toBeTruthy();
  });
});

describe("ResetPasswordPage", () => {
  const path = "/reset-password?uid=MQ&token=abc-123";
  const submit = (password = GOOD) => {
    typeInto("New password", password);
    typeInto("Confirm new password", password);
    fireEvent.click(screen.getByRole("button", { name: "Save new password" }));
  };

  it("reads uid and token from the emailed link and sends them with the new password", async () => {
    auth.resetPassword.mockResolvedValue({ message: "Password updated." });
    show(<ResetPasswordPage />, path);
    submit();
    expect(await screen.findByRole("heading", { name: "Password updated" })).toBeTruthy();
    expect(auth.resetPassword).toHaveBeenCalledWith({ uid: "MQ", token: "abc-123", password: GOOD });
  });

  it("shows the server's password error on the field", async () => {
    auth.resetPassword.mockRejectedValue(fail({ password: ["This password is too similar to your email."] }));
    show(<ResetPasswordPage />, path);
    submit();
    expect(await screen.findByText("This password is too similar to your email.")).toBeTruthy();
  });

  it("shows an invalid or expired link message with a way to ask for a new one", async () => {
    auth.resetPassword.mockRejectedValue(fail({ detail: ["This reset link is invalid or has expired."] }, "This reset link is invalid or has expired."));
    show(<ResetPasswordPage />, path);
    submit();
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("This reset link is invalid or has expired.");
    expect(screen.getByRole("link", { name: "Request a new link" })).toBeTruthy();
  });

  it("validates the password in the browser first", () => {
    show(<ResetPasswordPage />, path);
    submit("1234567890");
    expect(screen.getByText("The password cannot be only numbers.")).toBeTruthy();
    expect(auth.resetPassword).not.toHaveBeenCalled();
  });

  it("explains an incomplete link", () => {
    show(<ResetPasswordPage />, "/reset-password?uid=MQ");
    expect(screen.getByRole("alert").textContent).toMatch(/incomplete/i);
  });
});

describe("ForgotPasswordPage", () => {
  it("shows the server's neutral confirmation", async () => {
    auth.requestPasswordReset.mockResolvedValue({ message: "If that email has an account, a reset link is on its way." });
    show(<ForgotPasswordPage />);
    typeInto("Email", "someone@example.com");
    fireEvent.click(screen.getByRole("button", { name: "Send reset link" }));
    expect(await screen.findByText(/reset link is on its way/i)).toBeTruthy();
    expect(auth.requestPasswordReset).toHaveBeenCalledWith("someone@example.com");
  });

  it("shows a server error", async () => {
    auth.requestPasswordReset.mockRejectedValue(Object.assign(new Error("x"), { status: 429, fieldErrors: {}, friendly: "Request was throttled." }));
    show(<ForgotPasswordPage />);
    typeInto("Email", "someone@example.com");
    fireEvent.click(screen.getByRole("button", { name: "Send reset link" }));
    expect((await screen.findByRole("alert")).textContent).toBe("Request was throttled.");
  });
});

describe("VerifyEmailPage", () => {
  it("sends the key from the link exactly once and confirms", async () => {
    auth.verifyEmail.mockResolvedValue({ email_verified: true });
    show(<VerifyEmailPage />, "/verify-email?key=abc:def");
    expect(await screen.findByText(/your email is verified/i)).toBeTruthy();
    expect(auth.verifyEmail).toHaveBeenCalledTimes(1);
    expect(auth.verifyEmail).toHaveBeenCalledWith("abc:def");
  });

  it("shows the server's message for a bad link", async () => {
    auth.verifyEmail.mockRejectedValue(Object.assign(new Error("x"), { status: 400, fieldErrors: {}, friendly: "This verification link is invalid or has expired." }));
    show(<VerifyEmailPage />, "/verify-email?key=bad");
    await waitFor(() => expect(screen.getByRole("alert").textContent).toBe("This verification link is invalid or has expired."));
  });

  it("explains a link without a key", () => {
    show(<VerifyEmailPage />, "/verify-email");
    expect(screen.getByRole("alert").textContent).toMatch(/incomplete/i);
    expect(auth.verifyEmail).not.toHaveBeenCalled();
  });
});
