import { afterEach, describe, expect, it, vi } from "vitest";

describe("News feature flag", () => {
  afterEach(() => { vi.unstubAllEnvs(); vi.resetModules(); });

  it("is OFF by default, so nothing about News appears and the original flags are unchanged", async () => {
    vi.resetModules();
    const f = await import("../features");
    expect(f.FEATURE_NEWS).toBe(false);
    expect(f.FEATURES).toEqual({ marketplace: true, videoTools: true, academy: true });
    expect(f.EXTENSION_NAV_LINKS.some((l) => l.to === "/news")).toBe(false);
    expect(f.ADMIN_EXTENSION_LINKS.some((l) => l.to === "/admin/news")).toBe(false);
    const routes = await import("../features/news/routes");
    expect(routes.publicNewsRoutes).toEqual([]);
    expect(routes.adminNewsRoutes).toEqual([]);
  });

  it("turns on only for the exact value true, adding the links and routes", async () => {
    vi.stubEnv("VITE_FEATURE_NEWS", "yes");
    vi.resetModules();
    expect((await import("../features")).FEATURE_NEWS).toBe(false);
    vi.stubEnv("VITE_FEATURE_NEWS", "TRUE");
    vi.resetModules();
    const f = await import("../features");
    expect(f.FEATURE_NEWS).toBe(true);
    expect(f.EXTENSION_NAV_LINKS.map((l) => l.to)).toContain("/news");
    expect(f.ADMIN_EXTENSION_LINKS.map((l) => l.to)).toContain("/admin/news");
    const routes = await import("../features/news/routes");
    expect(routes.publicNewsRoutes.map((r) => r.path)).toEqual(["/news", "/news/category/:slug", "/news/search", "/news/report", "/news/:slug"]);
    expect(routes.adminNewsRoutes.every((r) => r.path.startsWith("news"))).toBe(true);
  });
});