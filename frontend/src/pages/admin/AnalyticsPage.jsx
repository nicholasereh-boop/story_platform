import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { analyticsDaily, analyticsOverview, analyticsStories, analyticsTraffic } from "../../api";
import LineChart from "../../components/charts/LineChart";
import QueryState from "../../components/public/QueryState";
import { DEVICE_LABELS, KPIS, formatChange, share } from "../../utils/analytics";
import { num } from "../../utils/format";

const RANGES = [7, 30, 90];
const GRANULARITIES = [
  { value: "day", label: "Daily" },
  { value: "week", label: "Weekly" },
  { value: "month", label: "Monthly" },
];

function KpiTile({ label, value, change }) {
  const c = formatChange(change);
  return (
    <li className="kpi">
      <p className="kpi-label">{label}</p>
      <p className="kpi-value">{num(value)}</p>
      <p className={`kpi-change ${c.direction}`}>
        <span aria-hidden="true">{c.text}</span>
        <span className="sr-only">{c.spoken}</span>
      </p>
    </li>
  );
}

// Horizontal bars with the number printed next to them (never colour or length alone).
function BarList({ rows, valueLabel }) {
  const top = Math.max(1, ...rows.map((r) => r.value));
  return (
    <ul className="bar-list">
      {rows.map((r) => (
        <li key={r.label}>
          <span className="bar-label">{r.label}</span>
          <span className="bar-track" aria-hidden="true"><span className="bar-fill" style={{ width: `${(r.value / top) * 100}%` }} /></span>
          <span className="bar-value">{num(r.value)}<span className="sr-only"> {valueLabel}</span>{r.note ? <span className="muted small"> {r.note}</span> : null}</span>
        </li>
      ))}
    </ul>
  );
}

const Skeleton = ({ height = 120 }) => <div className="skeleton-block" style={{ height }} aria-hidden="true" />;

// Admin > Analytics. Everything shown is an aggregate: no visitor can be identified from it.
export default function AnalyticsPage() {
  const [days, setDays] = useState(30);
  const [granularity, setGranularity] = useState("day");

  const overview = useQuery({ queryKey: ["admin", "analytics", "overview", days], queryFn: () => analyticsOverview({ days }) });
  const daily = useQuery({ queryKey: ["admin", "analytics", "daily", days, granularity], queryFn: () => analyticsDaily({ days, granularity }) });
  const stories = useQuery({ queryKey: ["admin", "analytics", "stories", days], queryFn: () => analyticsStories({ days, limit: 10 }) });
  const traffic = useQuery({ queryKey: ["admin", "analytics", "traffic", days], queryFn: () => analyticsTraffic({ days }) });

  return (
    <div className="analytics-page">
      <div className="page-head">
        <h1>Analytics</h1>
      </div>

      <div className="analytics-controls">
        <div role="group" aria-label="Date range" className="tabs">
          {RANGES.map((d) => (
            <button key={d} type="button" aria-pressed={days === d} className={days === d ? "active" : undefined} onClick={() => setDays(d)}>
              Last {d} days
            </button>
          ))}
        </div>
        <div role="group" aria-label="Group by" className="tabs">
          {GRANULARITIES.map((g) => (
            <button key={g.value} type="button" aria-pressed={granularity === g.value} className={granularity === g.value ? "active" : undefined} onClick={() => setGranularity(g.value)}>
              {g.label}
            </button>
          ))}
        </div>
      </div>
      <p className="hint">All days are UTC and weeks start on Monday. Visits by robots, staff and visitors who opted out are not counted.</p>

      <section aria-labelledby="kpi-h">
        <h2 id="kpi-h" className="sr-only">Totals</h2>
        <QueryState query={overview} skeleton={<Skeleton height={96} />}>
          {(o) => (
            <>
              <ul className="kpi-grid">
                {KPIS.map((k) => <KpiTile key={k.key} label={k.label} value={o.current[k.key]} change={o.change[k.key]} />)}
              </ul>
              <p className="hint">
                Compared with the {o.previous_range.days} days before ({o.previous_range.from} to {o.previous_range.to}).
                {!o.current.unique_visitors_exact && " Visitor counts for this range are estimates because older page views were deleted."}
              </p>
              {o.current.page_views === 0 && o.current.unique_visitors === 0 && (
                <div className="notice info" role="status">No visits have been recorded in this period yet.</div>
              )}
            </>
          )}
        </QueryState>
      </section>

      <section className="chart-card">
        <QueryState query={daily} skeleton={<Skeleton height={260} />}>
          {(d) => <LineChart title="Visitors and page views" points={d.points} granularity={d.granularity} series={[{ key: "unique_visitors", label: "Visitors" }, { key: "page_views", label: "Page views" }]} />}
        </QueryState>
      </section>
      <section className="chart-card">
        <QueryState query={daily} skeleton={<Skeleton height={260} />}>
          {(d) => <LineChart title="Likes and comments" points={d.points} granularity={d.granularity} series={[{ key: "likes", label: "Likes" }, { key: "comments", label: "Comments" }]} />}
        </QueryState>
      </section>

      <section aria-labelledby="top-h">
        <h2 id="top-h">Top stories</h2>
        <QueryState query={stories} skeleton={<Skeleton />} isEmpty={(d) => d.stories.length === 0} empty={<div className="empty">No story views in this period.</div>}>
          {(d) => (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">Story</th>
                    <th scope="col" className="num">Views</th>
                    <th scope="col" className="num">Visitors</th>
                    <th scope="col" className="num">Likes</th>
                    <th scope="col" className="num">Comments</th>
                  </tr>
                </thead>
                <tbody>
                  {d.stories.map((s) => (
                    <tr key={s.id}>
                      <td>
                        <Link to={`/stories/${s.slug}`}>{s.title}</Link>{" "}
                        <Link className="small" to={`/admin/stories/${s.id}/edit`} aria-label={`Edit ${s.title}`}>Edit</Link>
                      </td>
                      <td className="num">{num(s.views)}</td>
                      <td className="num">{num(s.unique_visitors)}</td>
                      <td className="num">{num(s.likes)}</td>
                      <td className="num">{num(s.comments)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </QueryState>
      </section>

      <div className="analytics-split">
        <section aria-labelledby="ref-h">
          <h2 id="ref-h">Where visitors come from</h2>
          <QueryState query={traffic} skeleton={<Skeleton />} isEmpty={(d) => d.referrers.length === 0} empty={<div className="empty">No visits in this period.</div>}>
            {(d) => <BarList valueLabel="page views" rows={d.referrers.map((r) => ({ label: r.domain, value: r.page_views, note: `${num(r.visitors)} visitors` }))} />}
          </QueryState>
        </section>
        <section aria-labelledby="dev-h">
          <h2 id="dev-h">Devices</h2>
          <QueryState query={traffic} skeleton={<Skeleton />} isEmpty={(d) => d.devices.every((x) => x.page_views === 0)} empty={<div className="empty">No visits in this period.</div>}>
            {(d) => {
              const total = d.devices.reduce((t, x) => t + x.page_views, 0);
              return <BarList valueLabel="page views" rows={d.devices.map((x) => ({ label: DEVICE_LABELS[x.device] || x.device, value: x.page_views, note: `${share(x.page_views, total)}%` }))} />;
            }}
          </QueryState>
        </section>
      </div>
    </div>
  );
}
