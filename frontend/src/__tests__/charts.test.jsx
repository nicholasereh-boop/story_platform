import { describe, expect, it } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import LineChart from "../components/charts/LineChart";
import { labelIndexes, niceMax, xPositions, yTicks } from "../components/charts/scale";

const points = [
  { date: "2026-03-01", unique_visitors: 4, page_views: 9 },
  { date: "2026-03-02", unique_visitors: 7, page_views: 12 },
  { date: "2026-03-03", unique_visitors: 0, page_views: 3 },
];
const series = [{ key: "unique_visitors", label: "Visitors" }, { key: "page_views", label: "Page views" }];

describe("chart scale helpers", () => {
  it("rounds the maximum up to a tidy number", () => {
    expect(niceMax(0)).toBe(1);
    expect(niceMax(7)).toBe(10);
    expect(niceMax(100)).toBe(100);
    expect(niceMax(120)).toBe(200);
    expect(niceMax(430)).toBe(500);
  });
  it("makes evenly spaced ticks and x positions", () => {
    expect(yTicks(100)).toEqual([0, 25, 50, 75, 100]);
    expect(xPositions(3, 0, 10)).toEqual([0, 5, 10]);
    expect(xPositions(1, 0, 10)).toEqual([5]);
    expect(xPositions(0, 0, 10)).toEqual([]);
  });
  it("labels the first and last point and at most six in total", () => {
    expect(labelIndexes(3)).toEqual([0, 1, 2]);
    const picked = labelIndexes(30, 6);
    expect(picked.length).toBeLessThanOrEqual(6);
    expect(picked[0]).toBe(0);
    expect(picked[picked.length - 1]).toBe(29);
    expect([...picked].sort((a, b) => a - b)).toEqual(picked);
  });
});

describe("LineChart", () => {
  it("draws one line per series with one point per day, and a text summary", () => {
    const { container } = render(<LineChart title="Visitors and page views" points={points} series={series} />);
    expect(screen.getByRole("img", { name: /Visitors and page views/ })).toBeTruthy();
    const lines = container.querySelectorAll("polyline");
    expect(lines.length).toBe(2);
    expect(lines[0].getAttribute("points").split(" ").length).toBe(3);
    expect(lines[0].getAttribute("stroke-dasharray")).toBeFalsy(); // first series: solid
    expect(lines[1].getAttribute("stroke-dasharray")).toBeTruthy(); // second series: dashed, so colour is not the only cue
    expect(container.querySelector("desc").textContent).toContain("Visitors: 11 in total");
    expect(container.querySelector("title").textContent).toBe("Mar 1: 4 visitors");
    expect(screen.getByRole("list", { name: "Legend" }).textContent).toContain("Page views");
  });

  it("can be shown as a table and back", () => {
    const { container } = render(<LineChart title="Visitors and page views" points={points} series={series} />);
    const toggle = screen.getByRole("button", { name: "Show as table" });
    fireEvent.click(toggle);
    const table = screen.getByRole("table");
    expect(within(table).getAllByRole("row").length).toBe(4); // header + 3 days
    expect(within(table).getByText("Mar 2")).toBeTruthy();
    expect(container.querySelector("svg.chart-svg")).toBeNull();
    expect(screen.getByRole("button", { name: "Show as chart" }).getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(screen.getByRole("button", { name: "Show as chart" }));
    expect(container.querySelector("svg.chart-svg")).toBeTruthy();
  });

  it("labels weekly and monthly points clearly", () => {
    const week = [{ date: "2026-03-02", unique_visitors: 5 }];
    render(<LineChart title="Weekly" points={week} series={[series[0]]} granularity="week" />);
    expect(screen.getAllByText("Week of Mar 2").length).toBeGreaterThan(0);
  });

  it("shows an empty state instead of a flat chart when there is no data", () => {
    const zeros = points.map((p) => ({ ...p, unique_visitors: 0, page_views: 0 }));
    const { container } = render(<LineChart title="Empty" points={zeros} series={series} />);
    expect(screen.getByText("No data for this period.")).toBeTruthy();
    expect(container.querySelector("svg.chart-svg")).toBeNull();
    expect(screen.queryByRole("button")).toBeNull();
  });
});
