import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getStory } from "../../api";
import StoryRenderer from "../../components/StoryRenderer";
import { fmtDate } from "../../utils/format";

// Shows the story the way a reader will see it (same StoryRenderer the public site will use in Phase 7).
export default function StoryPreviewPage() {
  const { id } = useParams();
  const { data: story, isLoading, isError, error } = useQuery({
    queryKey: ["story", id, "preview"],
    queryFn: () => getStory(id),
    gcTime: 0, // always show the latest saved version
  });

  if (isLoading) return <p className="muted">Loading preview…</p>;
  if (isError) {
    return (
      <div className="notice error" role="alert">
        {error.status === 404 ? "That story does not exist." : error.friendly} <Link to="/admin/stories">Back to stories</Link>
      </div>
    );
  }

  return (
    <>
      <div className="preview-banner" role="status">
        <strong>Preview: status {story.status}</strong>
        <span className="muted"> — this is the last saved version.</span>
        <Link className="btn secondary small" to={`/admin/stories/${id}/edit`}>← Back to editor</Link>
      </div>
      <article className="story-page">
        {story.categories?.length > 0 && (
          <p className="kicker">{story.categories.map((c) => c.name).join(" · ")}</p>
        )}
        <h1 className="story-title">{story.title || "(Untitled)"}</h1>
        <p className="muted byline">
          {story.author ? `By ${story.author}` : ""} {story.published_at ? `· ${fmtDate(story.published_at)}` : ""}
        </p>
        {story.excerpt && <p className="lede">{story.excerpt}</p>}
        {story.cover?.url && (
          <figure className="story-cover">
            <img src={story.cover.url} alt={story.cover.alt_text || ""} />
          </figure>
        )}
        <StoryRenderer content={story.content_json} />
        {story.tags?.length > 0 && (
          <ul className="chips" aria-label="Tags">
            {story.tags.map((t) => <li key={t.id} className="chip">#{t.name}</li>)}
          </ul>
        )}
      </article>
    </>
  );
}
