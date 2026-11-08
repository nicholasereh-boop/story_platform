import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { SITE_NAME } from "../../config";
import { MAX_STREAM, STORIES_PER_REFRESH, STREAM_STEP, buildBatch, buildStream, timeAgo } from "../../utils/homeFeed";
import { formatPrice } from "../../utils/money";

const HERO_MS = 6000; // the big card changes to the next story every 6 seconds

function reducedMotion() {
  return typeof window !== "undefined" && typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function Source({ story }) {
  const name = story.author || SITE_NAME;
  const ago = timeAgo(story.published_at);
  return (
    <span className="hf-source">
      <span className="hf-badge" aria-hidden="true">{name.slice(0, 1).toUpperCase()}</span>
      <span className="hf-source-name">{name}</span>
      {ago ? <span className="hf-source-time">· {ago}</span> : null}
    </span>
  );
}

// ---------- the big card: changes from one story to the next, with arrows and dots ----------
function HeroCarousel({ items }) {
  const count = items.length;
  const [index, setIndex] = useState(0);
  const [userPaused, setUserPaused] = useState(reducedMotion);
  const [hovering, setHovering] = useState(false);
  const [focused, setFocused] = useState(false);
  const [tabVisible, setTabVisible] = useState(true);
  const active = Math.min(index, count - 1);
  const playing = count > 1 && !userPaused && !hovering && !focused && tabVisible;
  const go = (i) => setIndex(((i % count) + count) % count);

  useEffect(() => {
    if (!playing) return undefined;
    const id = setTimeout(() => setIndex((active + 1) % count), HERO_MS);
    return () => clearTimeout(id);
  }, [playing, active, count]);

  useEffect(() => {
    const onVisibility = () => setTabVisible(document.visibilityState !== "hidden");
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, []);

  const onKeyDown = (e) => {
    if (count < 2) return;
    if (e.key === "ArrowRight") { e.preventDefault(); go(active + 1); }
    if (e.key === "ArrowLeft") { e.preventDefault(); go(active - 1); }
  };

  return (
    <li className="hf-hero">
      <section
        className="hf-hero-box"
        aria-label="Top stories"
        aria-roledescription="carousel"
        onKeyDown={onKeyDown}
        onPointerEnter={(e) => { if (e.pointerType !== "touch") setHovering(true); }}
        onPointerLeave={(e) => { if (e.pointerType !== "touch") setHovering(false); }}
        onFocus={(e) => { try { if (e.target.matches(":focus-visible")) setFocused(true); } catch { setFocused(true); } }}
        onBlur={() => setFocused(false)}
      >
        {items.map((s, i) => (
          <Link
            key={s.id}
            to={`/stories/${s.slug}`}
            className={`hf-slide${i === active ? " is-active" : ""}`}
            tabIndex={i === active ? undefined : -1}
            aria-hidden={i === active ? undefined : "true"}
          >
            {s.cover?.url ? <img src={s.cover.url} alt="" loading={i === 0 ? "eager" : "lazy"} draggable="false" /> : <span className="hf-noimg" aria-hidden="true" />}
            <span className="hf-shade" aria-hidden="true" />
            <span className="hf-slide-text">
              <Source story={s} />
              <span className="hf-hero-title">{s.title}</span>
            </span>
          </Link>
        ))}
        {count > 1 && (
          <>
            <button type="button" className="hf-arrow prev" aria-label="Previous story" onClick={() => go(active - 1)}><span aria-hidden="true">‹</span></button>
            <button type="button" className="hf-arrow next" aria-label="Next story" onClick={() => go(active + 1)}><span aria-hidden="true">›</span></button>
            <div className="hf-dots">
              <button type="button" className="hf-pause" aria-label={userPaused ? "Play top stories" : "Pause top stories"} onClick={() => setUserPaused((p) => !p)}>
                <span aria-hidden="true">{userPaused ? "▶" : "❚❚"}</span>
              </button>
              {items.map((s, i) => (
                <button key={s.id} type="button" className="hf-dot" aria-label={`Show story ${i + 1} of ${count}`} aria-current={i === active ? "true" : undefined} onClick={() => go(i)} />
              ))}
            </div>
          </>
        )}
      </section>
    </li>
  );
}

// ---------- a normal story card ----------
function StoryTile({ story }) {
  return (
    <li className="hf-card">
      <Link to={`/stories/${story.slug}`}>
        <span className="hf-card-media">
          {story.cover?.url ? <img src={story.cover.url} alt="" loading="lazy" draggable="false" /> : <span className="hf-noimg" aria-hidden="true" />}
        </span>
        <span className="hf-card-body">
          <Source story={story} />
          <span className="hf-card-title">{story.title}</span>
          {story.reading_minutes ? <span className="hf-card-foot">{story.reading_minutes} min read</span> : null}
        </span>
      </Link>
    </li>
  );
}

// ---------- a marketplace product shown as a card inside the endless part ----------
function ProductTile({ project }) {
  return (
    <li className="hf-card hf-product">
      <Link to={`/marketplace/projects/${project.slug}`}>
        <span className="hf-card-media">
          {project.cover?.url ? <img src={project.cover.url} alt="" loading="lazy" draggable="false" /> : <span className="hf-noimg" aria-hidden="true">{project.title.slice(0, 1).toUpperCase()}</span>}
        </span>
        <span className="hf-card-body">
          <span className="hf-source">
            <span className="hf-badge hf-badge-code" aria-hidden="true">{"</>"}</span>
            <span className="hf-source-name">Source code</span>
            <span className="hf-source-time">· Marketplace</span>
          </span>
          <span className="hf-card-title">{project.title}</span>
          <span className="hf-card-foot hf-card-price">{priceLabel(project)}</span>
        </span>
      </Link>
    </li>
  );
}

// ---------- "Suggested for you": topics to browse ----------
function SuggestedBox({ categories }) {
  const top = [...(categories || [])].sort((a, b) => b.story_count - a.story_count).slice(0, 5);
  if (top.length === 0) return null;
  return (
    <li className="hf-widget hf-suggested">
      <h2><span aria-hidden="true">✦</span> Suggested for you</h2>
      <p className="hf-widget-note">Browse topics to see more of what you like</p>
      <ul className="hf-pills">
        {top.map((c) => (
          <li key={c.slug}><Link to={`/categories/${c.slug}`}><span>{c.name}</span><span className="hf-pill-count">{c.story_count}</span></Link></li>
        ))}
      </ul>
    </li>
  );
}

// ---------- source code products from the marketplace (new ones with every refresh) ----------
function priceLabel(project) {
  const offers = project.offers || [];
  const paid = offers.map((o) => Number(o.price)).filter((n) => n > 0);
  if (paid.length === 0) return offers.length ? "Free" : "";
  return `From ${formatPrice(Math.min(...paid), offers[0].currency)}`;
}

function ProductsBox({ products }) {
  if (!products || products.length === 0) return null;
  return (
    <li className="hf-widget hf-products">
      <h2><span aria-hidden="true">{"</>"}</span> Source code</h2>
      <ul className="hf-tiles">
        {products.map((p) => (
          <li key={p.id}>
            <Link to={`/marketplace/projects/${p.slug}`}>
              <span className="hf-tile-media">
                {p.cover?.url ? <img src={p.cover.url} alt="" loading="lazy" draggable="false" /> : <span className="hf-noimg" aria-hidden="true">{p.title.slice(0, 1).toUpperCase()}</span>}
              </span>
              <span className="hf-tile-title">{p.title}</span>
              <span className="hf-tile-price">{priceLabel(p)}</span>
            </Link>
          </li>
        ))}
      </ul>
      <Link className="hf-widget-more" to="/marketplace">Browse the marketplace →</Link>
    </li>
  );
}

// ---------- the whole feed ----------
const HAS_OBSERVER = typeof IntersectionObserver !== "undefined";

export default function HomeFeed({ stories, products = [], categories = [], hasMore = false, loadingMore = false, onLoadMore }) {
  const [batch, setBatch] = useState(0);
  const [visible, setVisible] = useState(STREAM_STEP); // how many story cards the endless part shows
  const [spinning, setSpinning] = useState(false);
  const timer = useRef(null);
  const sentinel = useRef(null);
  useEffect(() => () => clearTimeout(timer.current), []);

  const { hero, small, products: shownProducts } = buildBatch(stories, products, batch);
  const start = batch * STORIES_PER_REFRESH + STORIES_PER_REFRESH; // the endless part continues right after those stories
  const stream = buildStream(stories, { start, count: visible, exhausted: !hasMore, products, productStart: batch * 4 + 4 });
  const atCap = visible >= MAX_STREAM;

  const refresh = () => {
    setBatch((b) => b + 1);
    setVisible(STREAM_STEP);
    setSpinning(true);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setSpinning(false), 700);
    window.scrollTo?.({ top: 0, behavior: "smooth" });
  };
  const grow = useCallback(() => setVisible((v) => Math.min(MAX_STREAM, v + STREAM_STEP)), []);

  // Near the bottom: show more cards. The observer is set up again after every change, so if the sentinel is still in view
  // (tall screen, or more stories just arrived) it asks again.
  useEffect(() => {
    const el = sentinel.current;
    if (!HAS_OBSERVER || !el || atCap) return undefined;
    const io = new IntersectionObserver((entries) => { if (entries.some((e) => e.isIntersecting)) grow(); }, { rootMargin: "900px 0px" });
    io.observe(el);
    return () => io.disconnect();
  }, [grow, atCap, visible, stories.length, hasMore]);

  // Running out of loaded stories while more exist on the server: fetch the next page.
  useEffect(() => {
    if (hasMore && !loadingMore && start + visible > stories.length) onLoadMore?.();
  }, [hasMore, loadingMore, start, visible, stories.length, onLoadMore]);

  const [a, b, c, d] = small;
  return (
    <div className="hf">
      <button type="button" className={`hf-refresh${spinning ? " is-spinning" : ""}`} onClick={refresh}>
        <span className="hf-spin" aria-hidden="true">↻</span> Refresh stories
      </button>
      <p className="sr-only" role="status" aria-live="polite">{batch > 0 ? "Showing a new set of stories" : ""}</p>

      {/* key = batch: a refresh starts the big card over with its new stories */}
      <ul className="hf-grid" key={batch}>
        <HeroCarousel items={hero} />
        {a && <StoryTile story={a} />}
        {b && <StoryTile story={b} />}
        <SuggestedBox categories={categories} />
        {c && <StoryTile story={c} />}
        {d && <StoryTile story={d} />}
        <ProductsBox products={shownProducts} />
        {stream.map((e) => (e.type === "product" ? <ProductTile key={e.key} project={e.project} /> : <StoryTile key={e.key} story={e.story} />))}
      </ul>

      {!atCap && HAS_OBSERVER && <div ref={sentinel} className="hf-sentinel" aria-hidden="true" />}
      {!atCap && !HAS_OBSERVER && <div className="hf-more"><button type="button" className="hf-more-btn" onClick={grow}>Show more stories</button></div>}
      {loadingMore && <p className="hf-note" role="status">Loading more stories…</p>}
      {atCap && <p className="hf-note">That is plenty for now. Press “Refresh stories” for a new set.</p>}
    </div>
  );
}

export function FeedSkeleton() {
  return (
    <div className="hf" aria-hidden="true">
      <ul className="hf-grid">
        <li className="hf-hero hf-skeleton" />
        <li className="hf-card hf-skeleton" />
        <li className="hf-card hf-skeleton" />
        <li className="hf-card hf-skeleton" />
        <li className="hf-card hf-skeleton" />
        <li className="hf-card hf-skeleton" />
      </ul>
    </div>
  );
}