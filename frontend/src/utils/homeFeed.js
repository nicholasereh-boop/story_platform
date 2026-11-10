// Pure helpers for the home page feed (no React), so the rules are easy to test.
import { fmtDate } from "./format";

export const STORIES_PER_REFRESH = 9; // up to 5 in the big rotating card + 2 beside it + 2 in the next row
export const PRODUCTS_PER_REFRESH = 4;
export const MAX_HERO = 5;
export const STREAM_STEP = 12; // used by the story page's "more stories" feed: how many cards appear each time the reader scrolls near the bottom
export const MAX_STREAM = 600; // a safety stop for that endless feed
export const STREAM_STORIES = 24; // HOME page: story cards under the first rows. With the big card, the 4 beside it and 3 marketplace cards: 32 cards in all
export const FEED_CARDS = 32; // HOME page: cards in one page of the feed (the big rotating card counts as one)
export const PRODUCT_EVERY = 8; // one marketplace product card after every 7 story cards in the endless part

// `count` items starting at `start`, wrapping around the end of the list (never the same item twice in one answer).
export function takeCircular(list, start, count) {
  if (!list || list.length === 0) return [];
  const n = Math.min(count, list.length);
  return Array.from({ length: n }, (_, i) => list[(start + i) % list.length]);
}

// What one "page" of the feed shows. Every refresh (batch + 1) moves on to other stories and other products.
export function buildBatch(stories, products, batch) {
  const picked = takeCircular(stories, batch * STORIES_PER_REFRESH, STORIES_PER_REFRESH);
  const heroCount = Math.max(1, Math.min(MAX_HERO, picked.length - 4));
  return {
    hero: picked.slice(0, heroCount),
    small: picked.slice(heroCount, heroCount + 4),
    products: takeCircular(products, batch * PRODUCTS_PER_REFRESH, PRODUCTS_PER_REFRESH),
  };
}

// "3h", "14m", "2d", then a plain date for anything older than a month.
export function timeAgo(iso, now = Date.now()) {
  if (!iso) return "";
  const seconds = Math.max(0, (now - new Date(iso).getTime()) / 1000);
  if (Number.isNaN(seconds)) return "";
  if (seconds < 3600) return `${Math.max(1, Math.floor(seconds / 60))}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
  if (seconds < 30 * 86400) return `${Math.floor(seconds / 86400)}d`;
  return fmtDate(iso);
}

// The endless part under the first rows. `start` is the absolute position in the pool where it begins (right after the
// stories used by the big card and the smaller cards). While more pages can still be loaded it only shows stories that
// are already loaded; once the pool is complete it wraps around, so the feed never runs out. Marketplace products are
// mixed in after every 7 stories. Keys are unique even when a story comes round again.
export function buildStream(pool, { start, count, exhausted, products = [], productStart = 0, repeatProducts = true }) {
  if (!pool || pool.length === 0 || count <= 0) return [];
  const available = exhausted ? Infinity : Math.max(0, pool.length - start);
  const storyCount = Math.min(count, MAX_STREAM, available);
  const out = [];
  let p = 0;
  for (let i = 0; i < storyCount; i++) {
    if (products.length > 0 && i > 0 && i % PRODUCT_EVERY === PRODUCT_EVERY - 1 && (repeatProducts || p < products.length)) {
      out.push({ type: "product", key: `p-${p}`, project: products[(productStart + p) % products.length] });
      p += 1;
    }
    out.push({ type: "story", key: `s-${i}`, story: pool[(start + i) % pool.length] });
  }
  return out;
}
