import { Link } from "react-router-dom";
import { formatDate } from "../utils/text";

export default function ArticleCard({ article, lead = false }) {
  const img = article.lead_image;
  return (
    <li className={lead ? "nw-card nw-card-lead" : "nw-card"}>
      {img?.url && <Link to={`/news/${article.slug}`} tabIndex={-1} aria-hidden="true"><img src={img.url} alt="" loading="lazy" className="nw-card-img" /></Link>}
      <div className="nw-card-text">
        <p className="nw-kicker">
          {article.is_breaking && <span className="nw-breaking">Breaking</span>}
          {article.category && <Link to={`/news/category/${article.category.slug}`}>{article.category.name}</Link>}
        </p>
        <h3 className="nw-card-title"><Link to={`/news/${article.slug}`}>{article.title}</Link></h3>
        {article.standfirst && <p className="nw-card-sub">{article.standfirst}</p>}
        <p className="nw-meta">{article.source?.name}{article.published_at ? ` · ${formatDate(article.published_at)}` : ""}</p>
      </div>
    </li>
  );
}
