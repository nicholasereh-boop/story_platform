import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

vi.mock("../api", () => ({
  analyticsOverview: vi.fn(), analyticsDaily: vi.fn(), analyticsStories: vi.fn(), analyticsTraffic: vi.fn(),
}));
import * as api from "../api";
import AnalyticsPage from "../pages/admin/AnalyticsPage";

const stats = (v, p, s, r, l, c) => ({ unique_visitors: v, page_views: p, story_views: s, registered_users: r, likes: l, comments: c });
const overview = {
  range: { from: "2026-03-01", to: "2026-03-30", days: 30 },
  previous_range: { from: "2026-01-30", to: "2026-02-28", days: 30 },
  current: { ...stats(1234, 3456, 2222, 5, 30, 12), unique_visitors_exact: true },
  previous: { ...stats(1000, 3840, 0, 5, 20, 0), unique_visitors_exact: true },
  change: { unique_visitors: 23.4, page_views: -10, story_views: null, registered_users: 0, likes: 50, comments: null },
};
const daily = (granularity = "day") => ({
  granularity, range: overview.range,
  points: [
    { date: "2026-03-01", ...stats(4, 9, 6, 0, 1, 0) },
    { date: "2026-03-02", ...stats(7, 12, 8, 1, 2, 1) },
  ],
});
const stories = { range: overview.range, stories: [{ id: 7, title: "The Lighthouse", slug: "the-lighthouse", views: 321, unique_visitors: 210, likes: 9, comments: 4 }] };
const traffic = {
  range: overview.range,
  referrers: [{ domain: "Direct", page_views: 30, visitors: 20 }, { domain: "news.example", page_views: 10, visitors: 8 }],
  devices: [{ device: "desktop", page_views: 30 }, { device: "mobile", page_views: 20 }, { device: "tablet", page_views: 0 }, { device: "other", page_views: 0 }],
};
const zeroOverview = { ...overview, current: { ...stats(0, 0, 0, 0, 0, 0), unique_visitors_exact: true }, previous: { ...stats(0, 0, 0, 0, 0, 0), unique_visitors_exact: true }, change: Object.fromEntries(Object.keys(overview.change).map((k) => [k, null])) };

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(<QueryClientProvider client={client}><MemoryRouter><AnalyticsPage /></MemoryRouter></QueryClientProvider>);
}
function fill() {
  api.analyticsOverview.mockResolvedValue(overview);
  api.analyticsDaily.mockImplementation((p) => Promise.resolve(daily(p.granularity)));
  api.analyticsStories.mockResolvedValue(stories);
  api.analyticsTraffic.mockResolvedValue(traffic);
}

beforeEach(() => vi.clearAllMocks());

describe("AnalyticsPage", () => {
  it("shows loading placeholders first", () => {
    for (const fn of [api.analyticsOverview, api.analyticsDaily, api.analyticsStories, api.analyticsTraffic]) fn.mockReturnValue(new Promise(() => {}));
    show();
    expect(screen.getAllByRole("status", { name: "Loading" }).length).toBeGreaterThan(0);
  });

  it("shows the six tiles with the change versus the previous period", async () => {
    fill();
    const { container } = show();
    await waitFor(() => expect(container.querySelectorAll(".kpi").length).toBe(6));
    const [visitors, views, storyViews, accounts, likes, comments] = [...container.querySelectorAll(".kpi")].map((el) => el.textContent);
    expect(visitors).toContain("Visitors");
    expect(visitors).toContain("1,234");
    expect(visitors).toContain("▲ 23.4%");
    expect(views).toContain("3,456");
    expect(views).toContain("▼ 10%");
    expect(storyViews).toContain("No previous data");
    expect(accounts).toContain("No change");
    expect(likes).toContain("▲ 50%");
    expect(comments).toContain("No previous data");
  });

  it("lists top stories with links to the story and its editor, plus referrers and devices", async () => {
    fill();
    show();
    const link = await screen.findByRole("link", { name: "The Lighthouse" });
    expect(link.getAttribute("href")).toBe("/stories/the-lighthouse");
    expect(screen.getByRole("link", { name: "Edit The Lighthouse" }).getAttribute("href")).toBe("/admin/stories/7/edit");
    expect(screen.getByText("321")).toBeTruthy();
    expect(await screen.findByText("news.example")).toBeTruthy();
    expect(screen.getByText("Direct")).toBeTruthy();
    expect(screen.getByText("Desktop")).toBeTruthy();
    expect(screen.getByText("60%")).toBeTruthy(); // 30 of 50 page views
  });

  it("refetches when the range or the grouping changes", async () => {
    fill();
    show();
    await screen.findByRole("link", { name: "The Lighthouse" });
    expect(api.analyticsOverview).toHaveBeenLastCalledWith({ days: 30 });
    expect(screen.getByRole("button", { name: "Last 30 days" }).getAttribute("aria-pressed")).toBe("true");

    fireEvent.click(screen.getByRole("button", { name: "Last 7 days" }));
    await waitFor(() => expect(api.analyticsOverview).toHaveBeenLastCalledWith({ days: 7 }));
    expect(api.analyticsStories).toHaveBeenLastCalledWith({ days: 7, limit: 10 });
    expect(api.analyticsTraffic).toHaveBeenLastCalledWith({ days: 7 });
    expect(screen.getByRole("button", { name: "Last 7 days" }).getAttribute("aria-pressed")).toBe("true");

    fireEvent.click(screen.getByRole("button", { name: "Weekly" }));
    await waitFor(() => expect(api.analyticsDaily).toHaveBeenLastCalledWith({ days: 7, granularity: "week" }));
    expect(screen.getByRole("button", { name: "Weekly" }).getAttribute("aria-pressed")).toBe("true");
  });

  it("shows an error with a retry button when the data cannot be loaded", async () => {
    fill();
    api.analyticsOverview.mockRejectedValueOnce(Object.assign(new Error("x"), { friendly: "Cannot reach the server." }));
    show();
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Cannot reach the server.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(api.analyticsOverview).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
  });

  it("shows friendly empty states when nothing has been recorded", async () => {
    api.analyticsOverview.mockResolvedValue(zeroOverview);
    api.analyticsDaily.mockResolvedValue({ granularity: "day", range: overview.range, points: daily().points.map((p) => ({ ...p, ...stats(0, 0, 0, 0, 0, 0) })) });
    api.analyticsStories.mockResolvedValue({ range: overview.range, stories: [] });
    api.analyticsTraffic.mockResolvedValue({ range: overview.range, referrers: [], devices: traffic.devices.map((d) => ({ ...d, page_views: 0 })) });
    show();
    expect(await screen.findByText(/No visits have been recorded in this period yet/)).toBeTruthy();
    expect(await screen.findByText("No story views in this period.")).toBeTruthy();
    expect((await screen.findAllByText("No data for this period.")).length).toBe(2); // both charts
    expect((await screen.findAllByText("No visits in this period.")).length).toBe(2); // referrers and devices
  });
});
