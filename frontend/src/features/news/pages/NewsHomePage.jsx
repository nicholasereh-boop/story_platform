import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useDocumentMeta } from "../../../hooks/useDocumentMeta";
import { getNewsBreaking, getNewsFeatured, listNewsArticles } from "../api/news";
import ArticleCard from "../components/ArticleCard";
import NewsNav from "../components/NewsNav";
import "../news.css";

export default function NewsHomePage() {
  useDocumentMeta({ title: "News", description: "The latest news, with full articles and clear credit to every source." });
  const breaking = useQuery({ queryKey: ["news", "breaking"], queryFn: getNewsBreaking });
  const featured = useQuery({ queryKey: ["news", "featured"], queryFn: getNewsFeatured });
  const latest = useQuery({ queryKey: ["news", "latest"], queryFn: () => listNewsArticles({ page_size: 12 }) });
  const items = latest.data?.items || [];
  const lead = (featured.data || [])[0];
  const rest = items.filter((a) => a.slug !== lead?.slug);
  const failed = latest.isError;
  return (
    <div className="nw-page">
      <h1 className="nw-h1">News</h1>
      <NewsNav />
      {(breaking.data || []).length > 0 && (
        <section className="nw-breaking-bar" aria-label="Breaking news">
          <strong>Breaking</strong>
          <ul>{breaking.data.map((a) => <li key={a.slug}><Link to={`/news/${a.slug}`}>{a.title}</Link></li>)}</ul>
        </section>
      )}
      {latest.isLoading && <p className="nw-muted">Loading the latest news…</p>}
      {failed && <p className="nw-error" role="alert">Could not load the news. Please try again.</p>}
      {lead && <ul className="nw-list nw-lead"><ArticleCard article={lead} lead /></ul>}
      {latest.data && rest.length === 0 && !lead && <p className="nw-empty">No news has been published yet.</p>}
      {rest.length > 0 && (
        <section aria-label="Latest news">
          <h2 className="nw-h2">Latest</h2>
          <ul className="nw-list">{rest.map((a) => <ArticleCard key={a.slug} article={a} />)}</ul>
          <p><Link to="/news/search?q=">More news →</Link></p>
        </section>
      )}
    </div>
  );
}
