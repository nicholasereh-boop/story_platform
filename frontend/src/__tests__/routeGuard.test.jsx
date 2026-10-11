import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";

const auth = { user: null, ready: true, login: vi.fn() };
vi.mock("../auth/AuthContext", () => ({ useAuth: () => auth }));
vi.mock("../api", () => ({ providers: vi.fn().mockResolvedValue({ google: false }) }));

import RequireStaff from "../auth/RequireStaff";
import LoginPage from "../pages/LoginPage";
import { afterLoginPath, safeFrom } from "../utils/redirect";

const reader = { email: "r@example.com", is_staff: false, email_verified: true };
const staff = { email: "s@example.com", is_staff: true, email_verified: true };

function show(entry) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[entry]}>
        <Routes>
          <Route path="/" element={<p>home page</p>} />
          <Route path="/stories/x" element={<p>story x</p>} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/admin" element={<RequireStaff><p>admin area</p></RequireStaff>} />
          <Route path="/admin/stories" element={<p>admin stories</p>} />
          <Route path="/admin/comments" element={<RequireStaff><p>admin comments</p></RequireStaff>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  auth.user = null;
  auth.ready = true;
});

describe("admin guard", () => {
  it("sends a visitor to the login page", () => {
    show("/admin");
    expect(screen.getByRole("heading", { name: "Log in" })).toBeTruthy();
    expect(screen.getByText("Please log in to continue.")).toBeTruthy();
  });

  it("sends a reader away from the admin to the public site", () => {
    auth.user = reader;
    show("/admin");
    expect(screen.getByText("home page")).toBeTruthy();
    expect(screen.queryByText("admin area")).toBeNull();
  });

  it("lets staff in", () => {
    auth.user = staff;
    show("/admin");
    expect(screen.getByText("admin area")).toBeTruthy();
  });

  it("waits for the session check before deciding", () => {
    auth.ready = false;
    show("/admin");
    expect(screen.getByText("Loading…")).toBeTruthy();
  });
});

describe("login page", () => {
  const type = () => {
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "x@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "pw-pw-pw-pw-1" } });
    fireEvent.click(screen.getByRole("button", { name: "Log in" }));
  };

  it("lets a reader log in and sends them to the home page (no more 'staff only')", async () => {
    auth.login.mockResolvedValue(reader);
    show("/login");
    type();
    await waitFor(() => expect(screen.getByText("home page")).toBeTruthy());
    expect(screen.queryByText(/staff access only/i)).toBeNull();
  });

  it("sends a reader back to where they came from", async () => {
    auth.login.mockResolvedValue(reader);
    show({ pathname: "/login", state: { from: "/stories/x" } });
    type();
    await waitFor(() => expect(screen.getByText("story x")).toBeTruthy());
  });

  it("sends staff to the admin by default", async () => {
    auth.login.mockResolvedValue(staff);
    show("/login");
    type();
    await waitFor(() => expect(screen.getByText("admin stories")).toBeTruthy());
  });

  it("sends staff back to where they came from", async () => {
    auth.login.mockResolvedValue(staff);
    show({ pathname: "/login", state: { from: "/admin/comments" } });
    type();
    await waitFor(() => expect(screen.getByText("admin comments")).toBeTruthy());
  });

  it("does not show the login form to someone who is already logged in", () => {
    auth.user = reader;
    show("/login");
    expect(screen.getByText("home page")).toBeTruthy();
  });

  it("shows the server's message for wrong credentials", async () => {
    auth.login.mockRejectedValue(Object.assign(new Error("x"), { status: 400, fieldErrors: {}, friendly: "Incorrect email or password." }));
    show("/login");
    type();
    expect((await screen.findByRole("alert")).textContent).toBe("Incorrect email or password.");
  });
});

describe("redirect helpers", () => {
  it("only accepts same-site paths", () => {
    expect(safeFrom("/stories/x?y=1")).toBe("/stories/x?y=1");
    for (const bad of ["//evil.example", "https://evil.example", "javascript:alert(1)", "/\\evil", "", null, undefined, 5]) {
      expect(safeFrom(bad), String(bad)).toBeNull();
    }
  });

  it("chooses the landing page by role", () => {
    expect(afterLoginPath(staff)).toBe("/admin/stories");
    expect(afterLoginPath(reader)).toBe("/");
    expect(afterLoginPath(reader, "/stories/x")).toBe("/stories/x");
    expect(afterLoginPath(staff, "//evil.example")).toBe("/admin/stories");
  });
});
