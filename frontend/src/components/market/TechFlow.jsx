import { Link } from "react-router-dom";

// A strip of technology names that flows past on its own. Each one filters the marketplace to that technology.
// It stops while hovered or focused; with "reduce motion" it is a plain row you scroll by hand.
const MIN_ITEMS = 12;

export default function TechFlow({ techs }) {
  if (!techs || techs.length === 0) return null;
  const lap = [];
  while (lap.length < MIN_ITEMS) lap.push(...techs); // repeat a short list so one lap fills a wide screen
  const seconds = Math.max(30, lap.length * 2.5);
  return (
    <nav className="mk-flow" aria-label="Browse by technology">
      <div className="mk-flow-track" style={{ "--mk-flow-seconds": `${seconds}s` }}>
        <ul className="mk-flow-group">
          {lap.map((t, i) => <li key={`a-${i}-${t.slug}`}><Link to={`/marketplace?tech=${t.slug}`}>{t.name}</Link></li>)}
        </ul>
        <ul className="mk-flow-group" aria-hidden="true">
          {lap.map((t, i) => <li key={`b-${i}-${t.slug}`}><Link to={`/marketplace?tech=${t.slug}`} tabIndex={-1}>{t.name}</Link></li>)}
        </ul>
      </div>
    </nav>
  );
}