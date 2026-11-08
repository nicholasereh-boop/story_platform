import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams, useSearchParams } from "react-router-dom";
import Pagination from "../../../components/Pagination";
import { useDocumentMeta } from "../../../hooks/useDocumentMeta";
import { listNewsArticles, listNewsCategories } from "../api/news";
import ArticleCard from "../components/ArticleCard";
import NewsNav from "../components/NewsNav";
import "../news.css";

// One list page for both /news/category/:slug and /news/search?q=...
export default function NewsListPage({ mode }) {
  const { slug } = useParams();
  const [params] = useSearchParams();
  const q = (params.get("q") || "").trim();
  const [page, setPage] = useState(1);
  const categories = useQuery({ queryKey: ["news", "categories"], queryFn: listNewsCategories, staleTime: 5 * 60_000 });
  const categoryName = mode === "category" ? (categories.data || []).find((c) => c.slug === slug)?.name : "";
  const title = mode === "search" ? (q ? `Search: ${q}` : "All news") : categoryName || "News";
  useDocumentMeta({ title: `${title} — News`, description: `News: ${title}`, robots: mode === "search" ? "noindex,follow" : "index,follow" });
  const tooShort = mode === "search" && q.length === 1;
  const list = useQuery({
    queryKey: ["news", "list", { mode, slug, q, page }],
    queryFn: () => listNewsArticles({ page, ...(mode === "category" ? { category: slug } : {}), ...(q ? { q } : {}) }),
    placeholderData: (previous) => previous,
    enabled: !tooShort,
  });
  const items = list.data?.items || [];
  return (
    <div className="nw-page">
      <h1 className="nw-h1">{title}</h1>
      <NewsNav initialQuery={mode === "search" ? q : ""} />
      {tooShort && <p className="nw-muted">Type at least two characters to search.</p>}
      {list.isLoading && <p className="nw-muted">Loading…</p>}
      {list.isError && <p className="nw-error" role="alert">Could not load the news. Please try again.</p>}
      {list.data && items.length === 0 && <p className="nw-empty">{q ? "No articles match your search." : "No articles here yet."}</p>}
      <ul className="nw-list">{items.map((a) => <ArticleCard key={a.slug} article={a} />)}</ul>
      {list.data && <Pagination pagination={list.data.pagination} onPage={(n) => { setPage(n); window.scrollTo?.(0, 0); }} />}
    </div>
  );
}
