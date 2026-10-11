import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { configureTracker, sendPageView, trackingAllowed } from "../analytics/tracker";
import { clearConsent, writeConsent } from "../privacy/consent";

let bodies;
beforeEach(() => {
  window.localStorage.clear(); window.sessionStorage.clear(); clearConsent();
  bodies = [];
  vi.stubGlobal("fetch", vi.fn((url, init) => { bodies.push(JSON.parse(init.body)); return Promise.resolve({}); }));
});
afterEach(() => { vi.unstubAllGlobals(); configureTracker({ mode: "notice", enabled: true }); });

describe("tracker payload and consent", () => {
  it("sends consent:true only in opt_in mode, and never any identity", () => {
    configureTracker({ mode: "opt_in", enabled: true });
    writeConsent("accepted");
    expect(trackingAllowed()).toBe(true);
    sendPageView({ pathname: "/stories/a" });
    expect(bodies[0].consent).toBe(true);
    expect(Object.keys(bodies[0]).sort()).toEqual(["consent", "path", "referrer", "session_id", "visitor_id"]);

    configureTracker({ mode: "opt_out", enabled: true });
    sendPageView({ pathname: "/stories/a" });
    expect("consent" in bodies[1]).toBe(false);
    configureTracker({ mode: "notice", enabled: true });
    sendPageView({ pathname: "/stories/a" });
    expect("consent" in bodies[2]).toBe(false);
  });

  it("trackingAllowed follows the mode and the choice", () => {
    configureTracker({ mode: "opt_in", enabled: true });
    expect(trackingAllowed()).toBe(false);
    writeConsent("accepted");
    expect(trackingAllowed()).toBe(true);
    writeConsent("rejected");
    expect(trackingAllowed()).toBe(false);
    configureTracker({ mode: "opt_out", enabled: true });
    expect(trackingAllowed()).toBe(false);
    clearConsent();
    expect(trackingAllowed()).toBe(true);
    configureTracker({ mode: "opt_out", enabled: false });
    expect(trackingAllowed()).toBe(false);
  });
});
