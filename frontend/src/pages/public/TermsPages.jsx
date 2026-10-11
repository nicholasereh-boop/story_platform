import { Link, useParams, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getCategories, getCategoryStories, getStories, getTags } from "../../api/public";
import Pagination from "../../components/Pagination";
import QueryState from "../../components/public/QueryState";
import StoryGrid, { StoryGridSkeleton } from "../../components/public/StoryGrid";
import { usePublicMeta } from "../../hooks/usePublicMeta";
import PublicNotFound from "./PublicNotFound";

const prettify = (slug) => slug.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
const countText = (n) => `${n} ${n === 1 ? "story" : "stories"}`;
const Skeleton = () => <div className="chips" aria-hidden="true">{Array.from({ length: 8 }, (_, i) => <span key={i} className="chip skeleton">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;</span>)}</div>;

// ---- /categories ----
export function CategoriesPage() {
  usePublicMeta({ title: "Categories", description: "Browse stories by category.", path: "/categories" });
  const query = useQuery({ queryKey: ["public", "categories"], queryFn: getCategories });
  return (
    <div className="container">
      <h1>Categories</h1>
      <QueryState query={query} skeleton={<Skeleton />} isEmpty={(d) => d.length === 0} empty={<div className="empty">No categories yet.</div>}>
        {(items) => (
          <ul className="term-grid">
            {items.map((c) => (
              <li key={c.slug} className="term-card">
                <h2><Link to={`/categories/${c.slug}`}>{c.name}</Link></h2>
                {c.description && <p>{c.description}</p>}
                <p className="muted small">{countText(c.story_count)}</p>
              </li>
            ))}
          </ul>
        )}
      </QueryState>
    </div>
  );
}

// ---- /tags ----
export function TagsPage() {
  usePublicMeta({ title: "Tags", description: "Browse stories by tag.", path: "/tags" });
  const query = useQuery({ queryKey: ["public", "tags"], queryFn: getTags });
  return (
    <div className="container">
      <h1>Tags</h1>
      <QueryState query={query} skeleton={<Skeleton />} isEmpty={(d) => d.length === 0} empty={<div className="empty">No tags yet.</div>}>
        {(items) => (
          <ul className="chips big">
            {items.map((t) => <li key={t.slug}><Link className="chip" to={`/tags/${t.slug}`}>#{t.name} <span className="count">{t.story_count}</span></Link></li>)}
          </ul>
        )}
      </QueryState>
    </div>
  );
}

// Shared body of the category and tag pages.
function TermStories({ heading, description, count, query, onPage }) {
  return (
    <div className="container">
      <h1>{heading}</h1>
      {description && <p className="lede">{description}</p>}
      {count != null && <p className="muted">{countText(count)}</p>}
      <QueryState query={query} skeleton={<StoryGridSkeleton />} isEmpty={(d) => d.items.length === 0} empty={<div className="empty">No stories here yet.</div>}>
        {(d) => (
          <>
            <StoryGrid stories={d.items} headingLevel={2} />
            <Pagination pagination={d.pagination} onPage={onPage} />
          </>
        )}
      </QueryState>
    </div>
  );
}

// ---- /categories/:slug ----
export function CategoryPage() {
  const { slug } = useParams();
  const [params, setParams] = useSearchParams();
  const page = Math.max(1, Number(params.get("page")) || 1);
  const categories = useQuery({ queryKey: ["public", "categories"], queryFn: getCategories });
  const stories = useQuery({
    queryKey: ["public", "category-stories", slug, page],
    queryFn: () => getCategoryStories(slug, { page }),
    retry: (n, err) => err.status !== 404 && n < 1,
    placeholderData: (prev) => prev,
  });
  const category = categories.data?.find((c) => c.slug === slug);
  const name = category?.name || prettify(slug);

  usePublicMeta({
    title: stories.isError ? undefined : name,
    description: category?.description || `Stories in ${name}.`,
    path: `/categories/${slug}`,
    robots: page > 1 ? "noindex,follow" : "index,follow",
  });

  if (stories.isError && stories.error?.status === 404) return <PublicNotFound what="category" />;
  return (
    <TermStories
      heading={name}
      description={category?.description}
      count={category?.story_count}
      query={stories}
      onPage={(p) => { setParams(p > 1 ? { page: String(p) } : {}); window.scrollTo?.(0, 0); }}
    />
  );
}

// ---- /tags/:slug ----
export function TagPage() {
  const { slug } = useParams();
  const [params, setParams] = useSearchParams();
  const page = Math.max(1, Number(params.get("page")) || 1);
  const tags = useQuery({ queryKey: ["public", "tags"], queryFn: getTags });
  const stories = useQuery({
    queryKey: ["public", "stories", { tag: slug, page }],
    queryFn: () => getStories({ tag: slug, page }),
    placeholderData: (prev) => prev,
  });
  const tag = tags.data?.find((t) => t.slug === slug);
  const name = tag?.name || prettify(slug);

  // A tag that has no public story is not in the list; the stories endpoint just answers with an empty page.
  const unknown = tags.isSuccess && !tag && stories.isSuccess && stories.data.items.length === 0;
  usePublicMeta({ title: unknown ? undefined : `#${name}`, description: `Stories tagged ${name}.`, path: `/tags/${slug}`, robots: page > 1 ? "noindex,follow" : "index,follow" });

  if (unknown) return <PublicNotFound what="tag" />;
  return (
    <TermStories
      heading={`#${name}`}
      count={tag?.story_count}
      query={stories}
      onPage={(p) => { setParams(p > 1 ? { page: String(p) } : {}); window.scrollTo?.(0, 0); }}
    />
  );
}
