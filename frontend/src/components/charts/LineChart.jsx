import { useId, useState } from "react";
import { num } from "../../utils/format";
import { pointLabel } from "../../utils/analytics";
import { labelIndexes, niceMax, xPositions, yTicks } from "./scale";

const W = 640, H = 240, LEFT = 48, RIGHT = 16, TOP = 12, BOTTOM = 32;
// Series are told apart by line style AND marker shape AND the legend text, not by colour alone.
const STYLES = [
  { dash: "", marker: "circle" },
  { dash: "6 4", marker: "square" },
];

function Marker({ shape, x, y }) {
  return shape === "square" ? <rect x={x - 3} y={y - 3} width="6" height="6" /> : <circle cx={x} cy={y} r="3.2" />;
}

// Accessible inline-SVG line chart (no chart library).
//   title        heading, also the accessible name
//   points       [{date, ...numbers}]
//   series       [{key, label}] (up to two)
//   granularity  "day" | "week" | "month" (for the labels)
// The chart can be swapped for a table with the "Show as table" button.
export default function LineChart({ title, points, series, granularity = "day", emptyText = "No data for this period." }) {
  const id = useId();
  const [asTable, setAsTable] = useState(false);
  const hasData = points.some((p) => series.some((s) => p[s.key] > 0));

  const max = niceMax(Math.max(0, ...points.flatMap((p) => series.map((s) => p[s.key] || 0))));
  const xs = xPositions(points.length, LEFT, W - RIGHT);
  const y = (v) => TOP + (H - TOP - BOTTOM) * (1 - v / max);
  const summary = hasData
    ? series.map((s) => `${s.label}: ${num(points.reduce((t, p) => t + (p[s.key] || 0), 0))} in total`).join("; ")
    : emptyText;

  return (
    <figure className="chart">
      <div className="chart-head">
        <figcaption id={`${id}-t`}>{title}</figcaption>
        {hasData && (
          <button type="button" className="btn ghost small" aria-pressed={asTable} onClick={() => setAsTable((v) => !v)}>
            {asTable ? "Show as chart" : "Show as table"}
          </button>
        )}
      </div>

      {!hasData && <p className="empty chart-empty">{emptyText}</p>}

      {hasData && asTable && (
        <div className="table-wrap">
          <table className="table">
            <caption className="sr-only">{title}</caption>
            <thead>
              <tr>
                <th scope="col">{granularity === "month" ? "Month" : granularity === "week" ? "Week" : "Day"}</th>
                {series.map((s) => <th key={s.key} scope="col" className="num">{s.label}</th>)}
              </tr>
            </thead>
            <tbody>
              {points.map((p) => (
                <tr key={p.date}>
                  <th scope="row">{pointLabel(p.date, granularity)}</th>
                  {series.map((s) => <td key={s.key} className="num">{num(p[s.key])}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {hasData && !asTable && (
        <>
          <ul className="chart-legend" aria-label="Legend">
            {series.map((s, i) => (
              <li key={s.key}>
                <svg width="34" height="12" aria-hidden="true" className={`series-${i}`}>
                  <line x1="0" y1="6" x2="34" y2="6" strokeDasharray={STYLES[i].dash} />
                  <g className="marker"><Marker shape={STYLES[i].marker} x={17} y={6} /></g>
                </svg>
                {s.label}
              </li>
            ))}
          </ul>
          <svg viewBox={`0 0 ${W} ${H}`} className="chart-svg" role="img" aria-labelledby={`${id}-t ${id}-d`}>
            <desc id={`${id}-d`}>{summary}. Use “Show as table” for every value.</desc>
            {yTicks(max).map((t) => (
              <g key={t}>
                <line className="grid" x1={LEFT} x2={W - RIGHT} y1={y(t)} y2={y(t)} />
                <text className="tick" x={LEFT - 6} y={y(t) + 4} textAnchor="end">{num(Math.round(t))}</text>
              </g>
            ))}
            {labelIndexes(points.length).map((i) => (
              <text key={i} className="tick" x={xs[i]} y={H - 10} textAnchor={i === 0 ? "start" : i === points.length - 1 ? "end" : "middle"}>
                {pointLabel(points[i].date, granularity)}
              </text>
            ))}
            {series.map((s, si) => (
              <g key={s.key} className={`series-${si}`}>
                <polyline points={points.map((p, i) => `${xs[i]},${y(p[s.key] || 0)}`).join(" ")} fill="none" strokeDasharray={STYLES[si].dash} />
                {points.length <= 40 && (
                  <g className="marker">
                    {points.map((p, i) => (
                      <g key={p.date}>
                        <title>{`${pointLabel(p.date, granularity)}: ${num(p[s.key])} ${s.label.toLowerCase()}`}</title>
                        <Marker shape={STYLES[si].marker} x={xs[i]} y={y(p[s.key] || 0)} />
                      </g>
                    ))}
                  </g>
                )}
              </g>
            ))}
          </svg>
        </>
      )}
    </figure>
  );
}
