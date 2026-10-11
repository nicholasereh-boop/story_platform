import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getCategories, getStories, getTags } from "../../api/public";
import Pagination from "../../components/Pagination";
import QueryState from "../../components/public/QueryState";
import StoryGrid, { StoryGridSkeleton } from "../../components/public/StoryGrid";
import { usePublicMeta } from "../../hooks/usePublicMeta";

// All stories. Filters and the page number live in the URL (?category=&tag=&page=), so links and the back button work.
export default function StoriesPage() {
  const [params, setParams] = useSearchParams();
  const category = params.get("category") || "";
  const tag = params.get("tag") || "";
  const page = Math.max(1, Number(params.get("page")) || 1);

  usePublicMeta({
    title: "All stories",
    description: "Every story we have published, newest first.",
    path: "/stories",
    robots: category || tag || page > 1 ? "noindex,follow" : "index,follow", // filtered views are not separate pages for search engines
  });

  const categories = useQuery({ queryKey: ["public", "categories"], queryFn: getCategories });
  const tags = useQuery({ queryKey: ["public", "tags"], queryFn: getTags });
  const stories = useQuery({
    queryKey: ["public", "stories", { category, tag, page }],
    queryFn: () => getStories({ category: category || undefined, tag: tag || undefined, page }),
    placeholderData: (prev) => prev,
  });

  const update = (changes) => {
    const next = new URLSearchParams(params);
    Object.entries(changes).forEach(([k, v]) => (v ? next.set(k, v) : next.delete(k)));
    setParams(next);
  };
  const filtered = Boolean(category || tag);

  return (
    <div className="container">
      <h1>Stories</h1>
      <form className="filters" onSubmit={(e) => e.preventDefault()} aria-label="Filter stories">
        <div className="field">
          <label htmlFor="f-category">Category</label>
          <select id="f-category" value={category} onChange={(e) => update({ category: e.target.value, page: "" })}>
            <option value="">All categories</option>
            {(categories.data || []).map((c) => <option key={c.slug} value={c.slug}>{c.name} ({c.story_count})</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor="f-tag">Tag</label>
          <select id="f-tag" value={tag} onChange={(e) => update({ tag: e.target.value, page: "" })}>
            <option value="">All tags</option>
            {(tags.data || []).map((t) => <option key={t.slug} value={t.slug}>{t.name} ({t.story_count})</option>)}
          </select>
        </div>
        {filtered && <button type="button" className="btn ghost small" onClick={() => update({ category: "", tag: "", page: "" })}>Clear filters</button>}
      </form>

      <QueryState
        query={stories}
        skeleton={<StoryGridSkeleton />}
        isEmpty={(d) => d.items.length === 0}
        empty={<div className="empty">{filtered ? "No stories match these filters." : "No stories have been published yet."}</div>}
      >
        {(d) => (
          <>
            <StoryGrid stories={d.items} headingLevel={2} />
            <Pagination pagination={d.pagination} onPage={(p) => { update({ page: p > 1 ? String(p) : "" }); window.scrollTo?.(0, 0); }} />
          </>
        )}
      </QueryState>
    </div>
  );
}
