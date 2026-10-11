import StoryCard from "./StoryCard";

export default function StoryGrid({ stories, headingLevel = 3 }) {
  return (
    <ul className="story-grid">
      {stories.map((story) => (
        <li key={story.id}>
          <StoryCard story={story} headingLevel={headingLevel} />
        </li>
      ))}
    </ul>
  );
}

// Grey placeholder cards while a list loads (no layout jump when the real cards arrive).
export function StoryGridSkeleton({ count = 6 }) {
  return (
    <ul className="story-grid" aria-hidden="true">
      {Array.from({ length: count }, (_, i) => (
        <li key={i} className="story-card skeleton-card">
          <div className="card-media skeleton" />
          <div className="card-body">
            <div className="skeleton line short" />
            <div className="skeleton line" />
            <div className="skeleton line" />
          </div>
        </li>
      ))}
    </ul>
  );
}
