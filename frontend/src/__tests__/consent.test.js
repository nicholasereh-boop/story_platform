import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CONSENT_KEY, CONSENT_TTL_MS, clearConsent, consentAllows, needsChoice, readConsent, writeConsent } from "../privacy/consent";

const DAY = 24 * 60 * 60 * 1000;
beforeEach(() => { window.localStorage.clear(); clearConsent(); });
afterEach(() => vi.restoreAllMocks());

describe("consent rules per mode", () => {
  it("notice: always allowed, never a banner", () => {
    for (const choice of [null, "accepted", "rejected"]) {
      expect(consentAllows("notice", choice)).toBe(true);
      expect(needsChoice("notice", choice)).toBe(false);
    }
  });
  it("opt_in: only after Accept", () => {
    expect(consentAllows("opt_in", null)).toBe(false);
    expect(consentAllows("opt_in", "rejected")).toBe(false);
    expect(consentAllows("opt_in", "accepted")).toBe(true);
    expect(needsChoice("opt_in", null)).toBe(true);
    expect(needsChoice("opt_in", "rejected")).toBe(false);
  });
  it("opt_out: on until Reject", () => {
    expect(consentAllows("opt_out", null)).toBe(true);
    expect(consentAllows("opt_out", "accepted")).toBe(true);
    expect(consentAllows("opt_out", "rejected")).toBe(false);
    expect(needsChoice("opt_out", null)).toBe(true);
  });
  it("an unknown mode behaves like notice", () => {
    expect(consentAllows("nonsense", null)).toBe(true);
    expect(needsChoice(undefined, null)).toBe(false);
  });
});

describe("remembering the choice", () => {
  it("stores the choice and reads it back", () => {
    expect(readConsent()).toBeNull();
    expect(writeConsent("accepted")).toBe(true);
    expect(readConsent()).toBe("accepted");
    expect(JSON.parse(window.localStorage.getItem(CONSENT_KEY)).choice).toBe("accepted");
  });
  it("lasts six months, then the visitor is asked again", () => {
    const now = Date.now();
    writeConsent("rejected", now);
    expect(readConsent(now + 179 * DAY)).toBe("rejected");
    expect(CONSENT_TTL_MS).toBe(180 * DAY);
    expect(readConsent(now + 181 * DAY)).toBeNull();
    expect(window.localStorage.getItem(CONSENT_KEY)).toBeNull(); // the expired entry is cleaned up
  });
  it("ignores garbage and entries dated in the future", () => {
    window.localStorage.setItem(CONSENT_KEY, "{not json");
    expect(readConsent()).toBeNull();
    window.localStorage.setItem(CONSENT_KEY, JSON.stringify({ choice: "maybe", at: Date.now() }));
    expect(readConsent()).toBeNull();
    window.localStorage.setItem(CONSENT_KEY, JSON.stringify({ choice: "accepted", at: Date.now() + 10 * DAY }));
    expect(readConsent()).toBeNull();
  });
  it("blocked storage never throws, and the choice still holds for this page", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("blocked"); });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("blocked"); });
    vi.spyOn(Storage.prototype, "removeItem").mockImplementation(() => { throw new Error("blocked"); });
    expect(readConsent()).toBeNull();
    expect(writeConsent("rejected")).toBe(false);
    expect(readConsent()).toBe("rejected"); // a Reject is not forgotten just because storage is blocked
    clearConsent();
    expect(readConsent()).toBeNull();
  });
});
