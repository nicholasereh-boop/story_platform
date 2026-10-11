import { useMemo, useRef } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getStory } from "../../api/public";
import StoryRenderer from "../../components/StoryRenderer";
import CommentSection from "../../components/engagement/CommentSection";
import LikeButton from "../../components/engagement/LikeButton";
import QueryState from "../../components/public/QueryState";
import RelatedStories from "../../components/public/RelatedStories";
import ShareButtons from "../../components/public/ShareButtons";
import { SITE_NAME } from "../../config";
import { useSignupPrompt } from "../../engagement/SignupPromptContext";
import { useReadTrigger } from "../../engagement/useReadTrigger";
import { usePublicMeta } from "../../hooks/usePublicMeta";
import { fmtDate } from "../../utils/format";
import { articleJsonLd } from "../../utils/seo";
import PublicNotFound from "./PublicNotFound";

function StorySkeleton() {
  return (
    <div className="story-page" aria-hidden="true">
      <div className="skeleton line short" />
      <div className="skeleton title-line" />
      <div className="skeleton line short" />
      <div className="skeleton cover-block" />
      {[0, 1, 2, 3].map((i) => <div key={i} className="skeleton line" />)}
    </div>
  );
}

export default function StoryPage() {
  const { slug } = useParams();
  const query = useQuery({
    queryKey: ["public", "story", slug],
    queryFn: () => getStory(slug),
    retry: (n, err) => err.status !== 404 && n < 1, // a 404 is an answer, not a glitch
  });
  const story = query.data;

  // About 60% of the way down the story, anonymous visitors may get the signup prompt (once, see SignupPromptContext).
  const sentinel = useRef(null);
  const { request } = useSignupPrompt();
  useReadTrigger(sentinel, () => request("read"), Boolean(story), slug);

  // SEO: seo_title/seo_description from the API (it already falls back to title/excerpt), cover as the social image.
  const origin = window.location.origin;
  const jsonLd = useMemo(() => (story ? articleJsonLd(story, { origin, siteName: SITE_NAME }) : undefined), [story, origin]);
  usePublicMeta({
    title: story?.seo_title,
    description: story?.seo_description,
    path: story?.canonical_path,
    image: story?.cover?.url,
    type: "article",
    robots: story ? "index,follow" : "noindex,follow",
    jsonLd,
  });

  return (
    <div className="container">
      <QueryState query={query} skeleton={<StorySkeleton />} notFound={<PublicNotFound what="story" />}>
        {(s) => (
          <article className="story-page">
            <span ref={sentinel} className="read-sentinel" aria-hidden="true" />
            {s.categories.length > 0 && (
              <p className="kicker">
                {s.categories.map((c, i) => (
                  <span key={c.slug}>{i > 0 && " · "}<Link to={`/categories/${c.slug}`}>{c.name}</Link></span>
                ))}
              </p>
            )}
            <h1 className="story-title">{s.title}</h1>
            <p className="byline muted">
              {[s.author && `By ${s.author}`, fmtDate(s.published_at), s.reading_minutes ? `${s.reading_minutes} min read` : null].filter(Boolean).join(" · ")}
            </p>
            {s.excerpt && <p className="lede">{s.excerpt}</p>}
            {s.cover?.url && (
              <figure className="story-cover">
                {/* Above the fold: load at once. width/height reserve the space so the page does not jump. */}
                <img src={s.cover.url} alt={s.cover.alt_text || ""} width={s.cover.width || undefined} height={s.cover.height || undefined} fetchpriority="high" />
              </figure>
            )}
            <StoryRenderer content={s.content_json} />
            {s.tags.length > 0 && (
              <ul className="chips" aria-label="Tags">
                {s.tags.map((t) => <li key={t.slug}><Link className="chip" to={`/tags/${t.slug}`}>#{t.name}</Link></li>)}
              </ul>
            )}
            <LikeButton slug={s.slug} initialCount={s.like_count} />
            <ShareButtons url={`${origin}${s.canonical_path}`} title={s.title} />
          </article>
        )}
      </QueryState>
      {story && <CommentSection slug={story.slug} count={story.comment_count} />}
      {story && <RelatedStories slug={slug} />}
    </div>
  );
}
