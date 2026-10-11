import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useNavigate } from "react-router-dom";

const auth = { ready: true, isStaff: false };
vi.mock("../auth/AuthContext", () => ({ useAuth: () => auth }));
vi.mock("../analytics/tracker", async (importOriginal) => ({ ...(await importOriginal()), sendPageView: vi.fn() }));

import { OPT_OUT_KEY, sendPageView } from "../analytics/tracker";
import { useTracker } from "../analytics/useTracker";

function Probe() {
  useTracker();
  const go = useNavigate();
  return (
    <>
      <button onClick={() => go("/stories/a")}>story</button>
      <button onClick={() => go("/search?q=secret")}>search</button>
      <button onClick={() => go("/admin/stories")}>admin</button>
      <button onClick={() => go("/login")}>login</button>
    </>
  );
}
const Harness = ({ at = "/" }) => (
  <MemoryRouter initialEntries={[at]}>
    <Routes><Route path="*" element={<Probe />} /></Routes>
  </MemoryRouter>
);
const paths = () => sendPageView.mock.calls.map(([arg]) => arg.pathname);

beforeEach(() => {
  vi.clearAllMocks();
  auth.ready = true;
  auth.isStaff = false;
  window.localStorage.clear();
});
afterEach(() => {
  delete navigator.doNotTrack;
  Object.defineProperty(document, "referrer", { value: "", configurable: true });
});

describe("useTracker", () => {
  it("sends one page view for the first page and one for every route change", () => {
    render(<Harness />);
    expect(paths()).toEqual(["/"]);
    fireEvent.click(screen.getByText("story"));
    expect(paths()).toEqual(["/", "/stories/a"]);
  });

  it("does not send the same page twice when the component re-renders", () => {
    const { rerender } = render(<Harness />);
    rerender(<Harness />);
    rerender(<Harness />);
    expect(paths()).toEqual(["/"]);
  });

  it("sends only the path, never the query string", () => {
    render(<Harness />);
    fireEvent.click(screen.getByText("search"));
    expect(paths()).toEqual(["/", "/search"]);
  });

  it("gives the browser's referrer to the first page only", () => {
    Object.defineProperty(document, "referrer", { value: "https://news.example/post", configurable: true });
    render(<Harness />);
    fireEvent.click(screen.getByText("story"));
    expect(sendPageView.mock.calls[0][0].referrer).toBe("https://news.example/post");
    expect(sendPageView.mock.calls[1][0].referrer).toBe("");
  });

  it("skips the admin, auth pages and everything else on the exclusion list", () => {
    render(<Harness at="/login" />);
    expect(sendPageView).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText("admin"));
    fireEvent.click(screen.getByText("login"));
    expect(sendPageView).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText("story"));
    expect(paths()).toEqual(["/stories/a"]);
  });

  it("never counts logged-in staff", () => {
    auth.isStaff = true;
    render(<Harness />);
    fireEvent.click(screen.getByText("story"));
    expect(sendPageView).not.toHaveBeenCalled();
  });

  it("waits until the login state is known, then sends the current page once", () => {
    auth.ready = false;
    const { rerender } = render(<Harness />);
    expect(sendPageView).not.toHaveBeenCalled();
    auth.ready = true;
    rerender(<Harness />);
    expect(paths()).toEqual(["/"]);
  });

  it("sends nothing when the browser asks not to be tracked", () => {
    Object.defineProperty(navigator, "doNotTrack", { value: "1", configurable: true });
    render(<Harness />);
    fireEvent.click(screen.getByText("story"));
    expect(sendPageView).not.toHaveBeenCalled();
  });

  it("sends nothing after the visitor opted out", () => {
    window.localStorage.setItem(OPT_OUT_KEY, "1");
    render(<Harness />);
    fireEvent.click(screen.getByText("story"));
    expect(sendPageView).not.toHaveBeenCalled();
  });
});
