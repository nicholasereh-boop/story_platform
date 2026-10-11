import { createElement } from "react";
import { Link } from "react-router-dom";
import { fmtDate } from "../../utils/format";

// One story in a grid. Works with a missing cover (a neutral block) and very long titles (clamped by CSS).
// `headingLevel` keeps the page's heading outline correct (3 under an <h2> section, 2 under the <h1> only).
export default function StoryCard({ story, headingLevel = 3 }) {
  const href = `/stories/${story.slug}`;
  const category = story.categories?.[0];
  const meta = [story.author, story.published_at ? fmtDate(story.published_at) : null, story.reading_minutes ? `${story.reading_minutes} min read` : null]
    .filter(Boolean);

  return (
    <article className="story-card">
      <Link to={href} className="card-media" tabIndex={-1} aria-hidden="true">
        {story.cover?.url ? (
          <img src={story.cover.url} alt="" width={story.cover.width || undefined} height={story.cover.height || undefined} loading="lazy" />
        ) : (
          <span className="card-placeholder" />
        )}
      </Link>
      <div className="card-body">
        {category && (
          <Link to={`/categories/${category.slug}`} className="kicker">
            {category.name}
          </Link>
        )}
        {createElement(headingLevel === 2 ? "h2" : "h3", { className: "card-title" }, <Link to={href}>{story.title}</Link>)}
        {story.excerpt && <p className="card-excerpt">{story.excerpt}</p>}
        {meta.length > 0 && <p className="card-meta">{meta.join(" · ")}</p>}
        {story.like_count > 0 && (
          <p className="card-likes" aria-label={`${story.like_count} ${story.like_count === 1 ? "like" : "likes"}`}>
            <span aria-hidden="true">♥ {story.like_count}</span>
          </p>
        )}
      </div>
    </article>
  );
}
