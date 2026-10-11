import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { searchStories } from "../../api/public";
import Pagination from "../../components/Pagination";
import QueryState from "../../components/public/QueryState";
import SearchBar from "../../components/public/SearchBar";
import StoryGrid, { StoryGridSkeleton } from "../../components/public/StoryGrid";
import { usePublicMeta } from "../../hooks/usePublicMeta";

const MIN = 2; // the server needs 2 to 100 characters

export default function SearchPage() {
  const [params, setParams] = useSearchParams();
  const q = (params.get("q") || "").trim();
  const page = Math.max(1, Number(params.get("page")) || 1);
  const tooShort = q.length < MIN;

  // Search results are not worth indexing: noindex, but let crawlers follow the story links.
  usePublicMeta({ title: q ? `Search: ${q}` : "Search", robots: "noindex,follow" });

  const query = useQuery({
    queryKey: ["public", "search", q, page],
    queryFn: () => searchStories(q, { page }),
    enabled: !tooShort,
    placeholderData: (prev) => prev,
  });

  return (
    <div className="container">
      <h1>Search</h1>
      <SearchBar />
      {tooShort ? (
        <p className="muted" role="status">{q ? `Type at least ${MIN} characters to search.` : "Type a word or two above to search all stories."}</p>
      ) : (
        <QueryState
          query={query}
          skeleton={<StoryGridSkeleton />}
          isEmpty={(d) => d.items.length === 0}
          empty={<div className="empty" role="status">No stories match “{q}”. Try a different word.</div>}
        >
          {(d) => (
            <>
              <p className="muted" role="status">{d.pagination.count} {d.pagination.count === 1 ? "story" : "stories"} found for “{q}”</p>
              <StoryGrid stories={d.items} headingLevel={2} />
              <Pagination
                pagination={d.pagination}
                onPage={(p) => { setParams({ q, ...(p > 1 ? { page: String(p) } : {}) }); window.scrollTo?.(0, 0); }}
              />
            </>
          )}
        </QueryState>
      )}
    </div>
  );
}
