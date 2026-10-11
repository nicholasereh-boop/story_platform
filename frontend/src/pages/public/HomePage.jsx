import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getCategories, getStories, getTags } from "../../api/public";
import QueryState from "../../components/public/QueryState";
import StoryGrid, { StoryGridSkeleton } from "../../components/public/StoryGrid";
import { SITE_DESCRIPTION, SITE_NAME } from "../../config";
import { usePublicMeta } from "../../hooks/usePublicMeta";
import { fmtDate } from "../../utils/format";

function Hero({ story }) {
  return (
    <section className="hero" aria-label="Featured story">
      <Link to={`/stories/${story.slug}`} className="hero-media" tabIndex={-1} aria-hidden="true">
        {story.cover?.url ? <img src={story.cover.url} alt="" width={story.cover.width || undefined} height={story.cover.height || undefined} fetchpriority="high" /> : <span className="card-placeholder" />}
      </Link>
      <div className="hero-body">
        {story.categories?.[0] && <Link to={`/categories/${story.categories[0].slug}`} className="kicker">{story.categories[0].name}</Link>}
        <h2><Link to={`/stories/${story.slug}`}>{story.title}</Link></h2>
        {story.excerpt && <p className="lede">{story.excerpt}</p>}
        <p className="card-meta">{[story.author, fmtDate(story.published_at), story.reading_minutes ? `${story.reading_minutes} min read` : null].filter(Boolean).join(" · ")}</p>
      </div>
    </section>
  );
}

export default function HomePage() {
  usePublicMeta({ home: true, description: SITE_DESCRIPTION, path: "/" });

  const featured = useQuery({ queryKey: ["public", "stories", { featured: 1, page_size: 1 }], queryFn: () => getStories({ featured: 1, page_size: 1 }) });
  const latest = useQuery({ queryKey: ["public", "stories", { page_size: 9 }], queryFn: () => getStories({ page_size: 9 }) });
  const categories = useQuery({ queryKey: ["public", "categories"], queryFn: getCategories });
  const tags = useQuery({ queryKey: ["public", "tags"], queryFn: getTags });

  // The hero is the latest FEATURED story; with none featured, the newest story takes its place.
  const heroStory = featured.data?.items?.[0] || latest.data?.items?.[0];
  const gridStories = (latest.data?.items || []).filter((s) => s.id !== heroStory?.id).slice(0, 8);
  const popularTags = [...(tags.data || [])].sort((a, b) => b.story_count - a.story_count || a.name.localeCompare(b.name)).slice(0, 12);

  return (
    <div className="container">
      <section className="intro">
        <h1>{SITE_NAME}</h1>
        <p className="muted">{SITE_DESCRIPTION}</p>
      </section>

      {/* Wait for BOTH queries so the hero does not flash the newest story and then swap to the featured one. */}
      <QueryState
        query={{ ...latest, isLoading: latest.isLoading || featured.isLoading }}
        skeleton={<StoryGridSkeleton count={6} />}
        isEmpty={(d) => d.items.length === 0}
        empty={<div className="empty">No stories have been published yet. Please check back soon.</div>}
      >
        {() => (
          <>
            {heroStory && <Hero story={heroStory} />}
            {gridStories.length > 0 && (
              <section aria-labelledby="latest-heading">
                <div className="section-head">
                  <h2 id="latest-heading">Latest stories</h2>
                  <Link to="/stories">All stories →</Link>
                </div>
                <StoryGrid stories={gridStories} />
              </section>
            )}
          </>
        )}
      </QueryState>

      {categories.data?.length > 0 && (
        <section aria-labelledby="cats-heading">
          <h2 id="cats-heading">Browse by category</h2>
          <ul className="chips big">
            {categories.data.map((c) => (
              <li key={c.slug}><Link className="chip" to={`/categories/${c.slug}`}>{c.name} <span className="count">{c.story_count}</span></Link></li>
            ))}
          </ul>
        </section>
      )}

      {popularTags.length > 0 && (
        <section aria-labelledby="tags-heading">
          <h2 id="tags-heading">Popular tags</h2>
          <ul className="chips">
            {popularTags.map((t) => (
              <li key={t.slug}><Link className="chip" to={`/tags/${t.slug}`}>#{t.name} <span className="count">{t.story_count}</span></Link></li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
