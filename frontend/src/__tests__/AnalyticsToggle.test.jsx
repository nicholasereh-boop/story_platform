import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import AnalyticsToggle from "../components/public/AnalyticsToggle";
import { OPT_OUT_KEY } from "../analytics/tracker";

beforeEach(() => window.localStorage.clear());
afterEach(() => {
  vi.restoreAllMocks();
  delete navigator.doNotTrack;
});

describe("AnalyticsToggle", () => {
  it("starts on, and switching it off is remembered", () => {
    render(<AnalyticsToggle />);
    const button = screen.getByRole("button", { name: "Analytics: on" });
    expect(button.getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(button);
    expect(screen.getByRole("button", { name: "Analytics: off" }).getAttribute("aria-pressed")).toBe("false");
    expect(window.localStorage.getItem(OPT_OUT_KEY)).toBe("1");
    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByRole("button", { name: "Analytics: on" })).toBeTruthy();
    expect(window.localStorage.getItem(OPT_OUT_KEY)).toBeNull();
  });

  it("shows off when the visitor opted out earlier", () => {
    window.localStorage.setItem(OPT_OUT_KEY, "1");
    render(<AnalyticsToggle />);
    expect(screen.getByRole("button", { name: "Analytics: off" })).toBeTruthy();
  });

  it("explains that Do Not Track is respected and offers no switch", () => {
    Object.defineProperty(navigator, "doNotTrack", { value: "1", configurable: true });
    render(<AnalyticsToggle />);
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.getByText(/your browser asks not to be tracked/i)).toBeTruthy();
  });

  it("does not crash when storage is blocked", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("blocked"); });
    render(<AnalyticsToggle />);
    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByRole("button", { name: "Analytics: off" })).toBeTruthy(); // holds for this page
  });
});
