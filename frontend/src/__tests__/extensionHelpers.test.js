import { afterEach, describe, expect, it, vi } from "vitest";
import { formatBytes, formatPrice } from "../utils/money";
import { filenameFromDisposition, explainBlobError } from "../utils/saveBlob";
import { safeImageSrc, firstError } from "../components/marketplace/shared";

describe("money", () => {
  it("formats prices and treats zero as free", () => {
    expect(formatPrice("49", "USD")).toBe("$49.00");
    expect(formatPrice("1234.5", "USD")).toBe("$1,234.50");
    expect(formatPrice("12")).toBe("$12.00"); // US dollars unless told otherwise
    expect(formatPrice("5000.50", "NGN")).toBe("₦5,000.50"); // projects priced in naira before the switch still read correctly
    expect(formatPrice("0.00")).toBe("Free");
    expect(formatPrice("nonsense")).toBe("Free");
    expect(formatPrice("12", "ZZZ")).toMatch(/12/);
  });
  it("formats sizes", () => {
    expect(formatBytes(500)).toBe("500 B");
    expect(formatBytes(2048)).toBe("2.0 KB");
    expect(formatBytes(5 * 1024 * 1024)).toBe("5.0 MB");
  });
});

describe("file names from the server", () => {
  it.each([
    ['attachment; filename="shop-frontend-v1.zip"', "shop-frontend-v1.zip"],
    ["attachment; filename=plain.zip", "plain.zip"],
    ["attachment; filename*=UTF-8''my%20file.zip", "my file.zip"],
    ['attachment; filename="../../etc/passwd"', "passwd"],
    ['attachment; filename="..\\..\\evil.exe"', "evil.exe"],
    ['attachment; filename="a<b>:c|d.zip"', "a_b_c_d.zip"],
    ['attachment; filename=".hidden"', "hidden"],
    ["attachment", "download"],
    [undefined, "download"],
  ])("%s -> %s", (header, expected) => {
    expect(filenameFromDisposition(header)).toBe(expected);
  });
  it("copes with broken encoding", () => {
    expect(filenameFromDisposition("attachment; filename*=UTF-8''%E0%A4%A; filename=ok.zip")).toBe("ok.zip");
  });
  it("reads the server's sentence out of an error Blob", async () => {
    const err = { friendly: "generic", response: { data: new Blob([JSON.stringify({ message: "Buy this package to download it." })]) } };
    expect((await explainBlobError(err)).friendly).toBe("Buy this package to download it.");
    const odd = { friendly: "generic", response: { data: new Blob(["<html>"]) } };
    expect((await explainBlobError(odd)).friendly).toBe("generic");
  });
});

describe("safe image addresses", () => {
  it.each([["/media/a.png", true], ["https://cdn.example/a.png", true], ["http://cdn.example/a.png", true],
    ["javascript:alert(1)", false], ["data:image/svg+xml,<svg onload=alert(1)>", false], ["//evil.example/a.png", false], ["", false], [null, false], [undefined, false]])
  ("%s", (src, ok) => {
    expect(Boolean(safeImageSrc(src))).toBe(ok);
  });
});

describe("firstError", () => {
  it("prefers the named field, then any field, then the general sentence", () => {
    const e = { friendly: "general", fieldErrors: { file: ["bad file"], other: ["other"] } };
    expect(firstError(e, "file")).toBe("bad file");
    expect(firstError(e, "missing")).toBe("bad file");
    expect(firstError({ friendly: "general", fieldErrors: {} })).toBe("general");
    expect(firstError(null)).toMatch(/went wrong/);
  });
});

describe("feature flags", () => {
  afterEach(() => { vi.unstubAllEnvs(); vi.resetModules(); });
  it("are on by default and off only when set to false", async () => {
    vi.resetModules();
    let f = await import("../features");
    expect(f.FEATURES).toEqual({ marketplace: true, videoTools: true });
    expect(f.EXTENSION_NAV_LINKS.map((l) => l.to)).toEqual(["/marketplace", "/video-tools"]);
    expect(f.ADMIN_EXTENSION_LINKS).toHaveLength(1);

    vi.stubEnv("VITE_FEATURE_MARKETPLACE", "false");
    vi.stubEnv("VITE_FEATURE_VIDEO_TOOLS", "FALSE");
    vi.resetModules();
    f = await import("../features");
    expect(f.FEATURES).toEqual({ marketplace: false, videoTools: false });
    expect(f.EXTENSION_NAV_LINKS).toEqual([]);
    expect(f.ADMIN_EXTENSION_LINKS).toEqual([]);

    vi.stubEnv("VITE_FEATURE_MARKETPLACE", "yes");
    vi.resetModules();
    f = await import("../features");
    expect(f.FEATURES.marketplace).toBe(true);
  });

  it("remove the routes when off, so those addresses fall through to the 404", async () => {
    vi.stubEnv("VITE_FEATURE_MARKETPLACE", "false");
    vi.stubEnv("VITE_FEATURE_VIDEO_TOOLS", "false");
    vi.resetModules();
    const r = await import("../extensionRoutes");
    expect(r.publicExtensionRoutes).toEqual([]);
    expect(r.adminExtensionRoutes).toEqual([]);
  });
});
