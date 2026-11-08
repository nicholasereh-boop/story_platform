import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { listProjects } from "../../api/marketplace";
import { getCategories, getStories } from "../../api/public";
import { SITE_NAME } from "../../config";
import { FEATURES } from "../../features";
import { MAX_STREAM, STREAM_STEP, buildStream, timeAgo } from "../../utils/homeFeed";
import { formatPrice } from "../../utils/money";

// "Discover more": the same endless feed as the home page (it keeps going as you scroll, has a Refresh button, and mixes in
// marketplace products), but every story is a wide LIST card: picture on the left, text on the right.
const HAS_OBSERVER = typeof IntersectionObserver !== "undefined";

// Every loaded page together, newest first, without the same story twice (and without the one being read).
function poolOf(pages, excludeId) {
  const seen = new Set();
  return pages.flatMap((p) => p.items).filter((s) => s.id !== excludeId && (seen.has(s.id) ? false : seen.add(s.id)));
}

function priceLabel(project) {
  const offers = project.offers || [];
  const paid = offers.map((o) => Number(o.price)).filter((n) => n > 0);
  if (paid.length === 0) return offers.length ? "Free" : "";
  return `From ${formatPrice(Math.min(...paid), offers[0].currency)}`;
}

function StoryRow({ story }) {
  const name = story.author || SITE_NAME;
  const ago = timeAgo(story.published_at);
  return (
    <li className="sf-card">
      <Link to={`/stories/${story.slug}`}>
        <span className="sf-thumb">
          {story.cover?.url ? <img src={story.cover.url} alt="" loading="lazy" draggable="false" /> : <span className="sf-noimg" aria-hidden="true">{story.title.slice(0, 1).toUpperCase()}</span>}
        </span>
        <span className="sf-text">
          <span className="sf-meta"><span className="sf-dot" aria-hidden="true" />{name}{ago ? ` · ${ago}` : ""}</span>
          <span className="sf-title">{story.title}</span>
          {story.excerpt ? <span className="sf-excerpt">{story.excerpt}</span> : null}
          {story.reading_minutes ? <span className="sf-foot">{story.reading_minutes} min read</span> : null}
        </span>
      </Link>
    </li>
  );
}

function ProductRow({ project }) {
  return (
    <li className="sf-card sf-product">
      <Link to={`/marketplace/projects/${project.slug}`}>
        <span className="sf-thumb">
          {project.cover?.url ? <img src={project.cover.url} alt="" loading="lazy" draggable="false" /> : <span className="sf-noimg" aria-hidden="true">{"</>"}</span>}
        </span>
        <span className="sf-text">
          <span className="sf-meta sf-meta-code">Source code · Marketplace</span>
          <span className="sf-title">{project.title}</span>
          {project.summary ? <span className="sf-excerpt">{project.summary}</span> : null}
          <span className="sf-foot sf-price">{priceLabel(project)}</span>
        </span>
      </Link>
    </li>
  );
}

export default function StoryMoreFeed({ excludeId }) {
  const stories = useInfiniteQuery({
    queryKey: ["public", "stories", "story-page-feed"],
    queryFn: ({ pageParam }) => getStories({ page_size: 24, page: pageParam }),
    initialPageParam: 1,
    getNextPageParam: (last) => (last.pagination?.has_next ? last.pagination.page + 1 : undefined),
  });
  const categories = useQuery({ queryKey: ["public", "categories"], queryFn: getCategories });
  const products = useQuery({
    queryKey: ["public", "home-products"],
    queryFn: () => listProjects({ page_size: 24 }),
    enabled: FEATURES.marketplace,
    staleTime: 60 * 1000,
    retry: false,
  });

  const [batch, setBatch] = useState(0);
  const [visible, setVisible] = useState(STREAM_STEP);
  const [spinning, setSpinning] = useState(false);
  const section = useRef(null);
  const sentinel = useRef(null);
  const timer = useRef(null);
  useEffect(() => () => clearTimeout(timer.current), []);

  const pool = poolOf(stories.data?.pages || [], excludeId);
  const hasMore = Boolean(stories.hasNextPage);
  const loadingMore = stories.isFetchingNextPage;
  const fetchNext = stories.fetchNextPage;
  const start = batch * STREAM_STEP; // a refresh starts further along the list
  const stream = buildStream(pool, { start, count: visible, exhausted: !hasMore, products: products.data?.items || [], productStart: batch * 3 });
  const atCap = visible >= MAX_STREAM;
  const topics = [...(categories.data || [])].sort((a, b) => b.story_count - a.story_count).slice(0, 6);

  const grow = useCallback(() => setVisible((v) => Math.min(MAX_STREAM, v + STREAM_STEP)), []);
  const refresh = () => {
    setBatch((b) => b + 1);
    setVisible(STREAM_STEP);
    setSpinning(true);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setSpinning(false), 700);
    section.current?.scrollIntoView?.({ behavior: "smooth", block: "start" });
  };

  useEffect(() => {
    const el = sentinel.current;
    if (!HAS_OBSERVER || !el || atCap || pool.length === 0) return undefined;
    const io = new IntersectionObserver((entries) => { if (entries.some((e) => e.isIntersecting)) grow(); }, { rootMargin: "900px 0px" });
    io.observe(el);
    return () => io.disconnect();
  }, [grow, atCap, visible, pool.length, hasMore]);

  useEffect(() => {
    if (hasMore && !loadingMore && start + visible > pool.length) fetchNext();
  }, [hasMore, loadingMore, start, visible, pool.length, fetchNext]);

  if (stories.isError || (stories.data && pool.length === 0)) return null; // a bonus section: hide it if there is nothing to show
  if (!stories.data) return null;

  return (
    <section className="sf" ref={section} aria-labelledby="sf-heading">
      <div className="sf-head">
        <h2 id="sf-heading">Discover more</h2>
        <button type="button" className={`sf-refresh${spinning ? " is-spinning" : ""}`} onClick={refresh}>
          <span className="sf-spin" aria-hidden="true">↻</span> Refresh stories
        </button>
      </div>
      <p className="sr-only" role="status" aria-live="polite">{batch > 0 ? "Showing a new set of stories" : ""}</p>

      {topics.length > 0 && (
        <ul className="sf-topics" aria-label="Browse topics">
          {topics.map((c) => <li key={c.slug}><Link to={`/categories/${c.slug}`}>{c.name}<span>{c.story_count}</span></Link></li>)}
        </ul>
      )}

      <ul className="sf-grid" key={batch}>
        {stream.map((e) => (e.type === "product" ? <ProductRow key={e.key} project={e.project} /> : <StoryRow key={e.key} story={e.story} />))}
      </ul>

      {!atCap && HAS_OBSERVER && <div ref={sentinel} className="sf-sentinel" aria-hidden="true" />}
      {!atCap && !HAS_OBSERVER && <div className="sf-more"><button type="button" className="sf-more-btn" onClick={grow}>Show more stories</button></div>}
      {loadingMore && <p className="sf-note" role="status">Loading more stories…</p>}
      {atCap && <p className="sf-note">That is plenty for now. Press “Refresh stories” for a new set.</p>}
    </section>
  );
}