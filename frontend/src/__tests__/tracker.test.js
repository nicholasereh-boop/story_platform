import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as t from "../analytics/tracker";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const setNav = (name, value) => Object.defineProperty(navigator, name, { value, configurable: true });
const blockStorage = () => {
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("blocked"); });
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("blocked"); });
  vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => { throw new Error("blocked"); });
};

beforeEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
});
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  for (const name of ["doNotTrack", "globalPrivacyControl", "sendBeacon"]) delete navigator[name];
});

describe("which pages are tracked", () => {
  it("never tracks the admin, auth pages or the account page", () => {
    for (const p of ["/admin", "/admin/stories", "/login", "/register", "/forgot-password", "/reset-password", "/verify-email", "/account"]) {
      expect(t.isExcludedPath(p), p).toBe(true);
    }
  });
  it("tracks public pages (and does not match look-alike prefixes)", () => {
    for (const p of ["/", "/stories", "/stories/a-story", "/privacy", "/search", "/administration", "/loginx"]) {
      expect(t.isExcludedPath(p), p).toBe(false);
    }
  });
});

describe("opt-out rules", () => {
  it("honours Do Not Track and Global Privacy Control", () => {
    expect(t.browserSaysNo()).toBe(false);
    setNav("doNotTrack", "1");
    expect(t.browserSaysNo()).toBe(true);
    expect(t.trackingAllowed()).toBe(false);
    delete navigator.doNotTrack;
    setNav("globalPrivacyControl", true);
    expect(t.browserSaysNo()).toBe(true);
  });

  it("remembers the footer opt-out", () => {
    expect(t.trackingAllowed()).toBe(true);
    expect(t.setOptedOut(true)).toBe(true);
    expect(t.isOptedOut()).toBe(true);
    expect(t.trackingAllowed()).toBe(false);
    t.setOptedOut(false);
    expect(t.trackingAllowed()).toBe(true);
  });

  it("does not crash when storage is blocked", () => {
    blockStorage();
    expect(t.isOptedOut()).toBe(false);
    expect(t.setOptedOut(true)).toBe(false);
    expect(t.trackingAllowed()).toBe(true);
  });
});

describe("anonymous ids", () => {
  it("keeps one visitor id in localStorage and one session id in sessionStorage", () => {
    const visitor = t.getVisitorId();
    expect(visitor).toMatch(UUID);
    expect(t.getVisitorId()).toBe(visitor);
    expect(window.localStorage.getItem(t.VISITOR_KEY)).toBe(visitor);
    const session = t.getSessionId();
    expect(session).toMatch(UUID);
    expect(window.sessionStorage.getItem(t.SESSION_KEY)).toBe(session);
    expect(session).not.toBe(visitor);
  });

  it("falls back to a one-off id when storage is blocked", () => {
    blockStorage();
    const a = t.getVisitorId();
    expect(a).toMatch(UUID);
    expect(t.getVisitorId()).not.toBe(a); // nothing was remembered: each view is a one-off visit
  });
});

describe("sendPageView", () => {
  it("uses sendBeacon with a JSON blob when it is available", () => {
    const beacon = vi.fn(() => true);
    setNav("sendBeacon", beacon);
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    t.sendPageView({ pathname: "/stories/a", referrer: "https://news.example/x" });
    expect(beacon).toHaveBeenCalledTimes(1);
    const [url, blob] = beacon.mock.calls[0];
    expect(url).toBe(t.COLLECT_URL);
    expect(blob).toBeInstanceOf(Blob);
    expect(blob.type).toBe("application/json");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("falls back to fetch with keepalive and sends only the expected fields", () => {
    setNav("sendBeacon", undefined);
    const fetchMock = vi.fn().mockResolvedValue({});
    vi.stubGlobal("fetch", fetchMock);
    t.sendPageView({ pathname: "/search", referrer: "" });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(t.COLLECT_URL);
    expect(init.keepalive).toBe(true);
    expect(init.method).toBe("POST");
    const body = JSON.parse(init.body);
    expect(Object.keys(body).sort()).toEqual(["path", "referrer", "session_id", "visitor_id"]);
    expect(body.path).toBe("/search"); // path only, never a query string
    expect(body.visitor_id).toMatch(UUID);
  });

  it("uses fetch when the beacon could not be queued", () => {
    setNav("sendBeacon", vi.fn(() => false));
    const fetchMock = vi.fn().mockResolvedValue({});
    vi.stubGlobal("fetch", fetchMock);
    t.sendPageView({ pathname: "/" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("never throws and never retries when the network or the browser fails", async () => {
    setNav("sendBeacon", vi.fn(() => { throw new Error("beacon failed"); }));
    const fetchMock = vi.fn().mockRejectedValue(new Error("offline"));
    vi.stubGlobal("fetch", fetchMock);
    expect(() => t.sendPageView({ pathname: "/" })).not.toThrow();
    setNav("sendBeacon", undefined);
    expect(() => t.sendPageView({ pathname: "/" })).not.toThrow();
    await Promise.resolve();
    expect(fetchMock).toHaveBeenCalledTimes(1); // one attempt, no retry loop
    vi.stubGlobal("fetch", vi.fn(() => { throw new Error("sync failure"); }));
    expect(() => t.sendPageView({ pathname: "/" })).not.toThrow();
  });

  it("still sends when storage is blocked", () => {
    blockStorage();
    setNav("sendBeacon", undefined);
    const fetchMock = vi.fn().mockResolvedValue({});
    vi.stubGlobal("fetch", fetchMock);
    t.sendPageView({ pathname: "/" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
