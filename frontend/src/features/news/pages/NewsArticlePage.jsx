import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { useDocumentMeta } from "../../../hooks/useDocumentMeta";
import { countNewsView, getNewsArticle, getNewsRelated } from "../api/news";
import ArticleBody from "../components/ArticleBody";
import ArticleCard from "../components/ArticleCard";
import NewsComments from "../components/NewsComments";
import NewsNav from "../components/NewsNav";
import { useNewsConfig } from "../hooks/useNewsConfig";
import { formatDate } from "../utils/text";
import "../news.css";

function Credit({ asset }) {
  const text = [asset.caption, asset.credit || asset.creator, asset.licence].filter(Boolean);
  return (
    <figure className="nw-figure">
      {asset.kind === "image" && asset.image?.url && <img src={asset.image.url} alt={asset.alt || ""} width={asset.image.width || undefined} height={asset.image.height || undefined} />}
      {asset.kind === "video" && asset.video_id && (
        <div className="nw-video"><iframe title={asset.alt || asset.caption || "Video"} src={`https://www.youtube-nocookie.com/embed/${encodeURIComponent(asset.video_id)}`} allow="encrypted-media; picture-in-picture" allowFullScreen loading="lazy" referrerPolicy="strict-origin-when-cross-origin" /></div>
      )}
      {text.length > 0 && <figcaption>{text.join(" · ")}</figcaption>}
    </figure>
  );
}

export default function NewsArticlePage() {
  const { slug } = useParams();
  const config = useNewsConfig();
  const article = useQuery({ queryKey: ["news", "article", slug], queryFn: () => getNewsArticle(slug), retry: false });
  const related = useQuery({ queryKey: ["news", "related", slug], queryFn: () => getNewsRelated(slug), enabled: Boolean(article.data) });
  const a = article.data;
  useDocumentMeta(a ? { title: a.title, description: a.standfirst || a.title, type: "article", canonical: `${window.location.origin}/news/${a.slug}`, robots: "index,follow" } : { title: "News", robots: "noindex" });

  // Some licences require a page-view counter: count one view per opened article, never block the page on it.
  const counted = a?.counter_required;
  useEffect(() => {
    if (counted) countNewsView(slug).catch(() => {});
  }, [counted, slug]);

  if (article.isLoading) return <div className="nw-page"><p className="nw-muted">Loading the article…</p></div>;
  if (article.isError || !a) {
    return (
      <div className="nw-page">
        <h1 className="nw-h1">Article not found</h1>
        <p className="nw-lede">This article does not exist or is no longer available.</p>
        <p><Link to="/news">← Back to the news</Link></p>
      </div>
    );
  }
  const lead = a.assets[0];
  const otherAssets = a.assets.slice(1);
  return (
    <div className="nw-page">
      <NewsNav />
      <article className="nw-article" lang={a.language || undefined}>
        <header>
          <p className="nw-kicker">
            {a.is_breaking && <span className="nw-breaking">Breaking</span>}
            {a.category && <Link to={`/news/category/${a.category.slug}`}>{a.category.name}</Link>}
          </p>
          <h1 className="nw-h1">{a.title}</h1>
          {a.standfirst && <p className="nw-standfirst">{a.standfirst}</p>}
          <p className="nw-byline">
            {a.author_name && <span>By {a.author_name} · </span>}
            <time dateTime={a.published_at}>{formatDate(a.published_at, true)}</time>
            {a.source_published_at && <span> · First published {formatDate(a.source_published_at)}</span>}
          </p>
        </header>
        {lead && <Credit asset={lead} />}
        <ArticleBody html={a.body} />
        {otherAssets.map((x) => <Credit key={x.id} asset={x} />)}
        <aside className="nw-attribution" aria-label="Source and licence">
          <p>{a.attribution}</p>
          {a.original_url && <p><a href={a.original_url} rel="noopener noreferrer nofollow" target="_blank">Read the original article</a></p>}
          {a.licence && <p className="nw-muted">Licence: {a.licence}</p>}
          <p className="nw-muted">
            Published by {a.source.name}.{" "}
            <Link to="/news/report">Report a copyright or accuracy problem</Link>
            {config.copyright_contact && <> or write to <a href={`mailto:${config.copyright_contact}`}>{config.copyright_contact}</a></>}.
          </p>
        </aside>
      </article>
      {config.comments && <NewsComments slug={a.slug} />}
      {(related.data || []).length > 0 && (
        <section aria-label="Related stories">
          <h2 className="nw-h2">Related stories</h2>
          <ul className="nw-list">{related.data.map((r) => <ArticleCard key={r.slug} article={r} />)}</ul>
        </section>
      )}
    </div>
  );
}
