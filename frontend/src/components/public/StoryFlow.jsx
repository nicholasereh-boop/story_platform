import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getStories } from "../../api/public";
import { fmtDate } from "../../utils/format";

// A box at the bottom of a page where other stories flow past, one after another, on their own. It stops while the reader
// hovers over it or tabs into it, and has a Pause button; with "reduce motion" on, it is a plain row to scroll by hand.
// Stories already shown on the page are left out when enough others remain. It is a bonus: if it cannot load, it is hidden.
const MIN_ITEMS = 10; // enough cards in one lap to fill even a very wide screen

function Card({ story, hidden }) {
  const meta = [story.author, story.published_at ? fmtDate(story.published_at) : null].filter(Boolean).join(" · ");
  return (
    <li className="flow-card">
      <Link to={`/stories/${story.slug}`} tabIndex={hidden ? -1 : undefined}>
        <span className="flow-thumb">
          {story.cover?.url ? <img src={story.cover.url} alt="" loading="lazy" draggable="false" /> : null}
        </span>
        <span className="flow-title">{story.title}</span>
        {meta ? <span className="flow-meta">{meta}</span> : null}
      </Link>
    </li>
  );
}

export default function StoryFlow({ exclude = [], title = "More stories to explore" }) {
  const [paused, setPaused] = useState(false);
  const query = useQuery({
    queryKey: ["public", "stories", { page_size: 12, flow: 1 }],
    queryFn: () => getStories({ page_size: 12 }),
    staleTime: 60 * 1000,
  });

  const all = query.data?.items || [];
  const skip = new Set(exclude);
  const others = all.filter((s) => !skip.has(s.id));
  const stories = others.length >= 3 ? others : all;
  if (query.isError || stories.length === 0) return null;

  const lap = [];
  while (lap.length < MIN_ITEMS) lap.push(...stories); // repeat a short list so the lap is long enough
  const seconds = Math.max(30, lap.length * 4);

  return (
    <section className={`flow${paused ? " is-paused" : ""}`} aria-labelledby="flow-heading">
      <div className="flow-head">
        <h2 id="flow-heading">{title}</h2>
        <button type="button" className="flow-toggle" aria-pressed={paused} onClick={() => setPaused((p) => !p)}>
          {paused ? "▶ Play" : "❚❚ Pause"}
        </button>
      </div>
      <div className="flow-viewport">
        <div className="flow-track" style={{ "--flow-seconds": `${seconds}s` }}>
          <ul className="flow-group">{lap.map((s, i) => <Card key={`a-${i}-${s.id}`} story={s} />)}</ul>
          <ul className="flow-group" aria-hidden="true">{lap.map((s, i) => <Card key={`b-${i}-${s.id}`} story={s} hidden />)}</ul>
        </div>
      </div>
    </section>
  );
}