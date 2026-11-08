import { Link } from "react-router-dom";
import { PriceTag, safeImageSrc } from "../marketplace/shared";

// One project on the marketplace. variant: "feature" (big, picture behind the text), "card" (normal), "compact" (narrow, for rails).
export default function MarketCard({ project, variant = "card" }) {
  const src = safeImageSrc(project.cover?.url);
  const seller = project.seller || "";
  return (
    <li className={`mk-card mk-${variant}`}>
      <Link className="mk-card-link" to={`/marketplace/projects/${project.slug}`}>
        <span className="mk-media">
          {src ? <img src={src} alt={project.cover.alt_text || ""} loading="lazy" draggable="false" width={project.cover.width || undefined} height={project.cover.height || undefined} /> : <span className="mk-noimg" aria-hidden="true">{project.title.slice(0, 1).toUpperCase()}</span>}
          {variant === "feature" ? <span className="mk-flag" aria-hidden="true">✨ Featured</span> : null}
          {project.has_video ? <span className="mk-badge" aria-label="Has a video">▶ Video</span> : null}
        </span>
        <span className="mk-body">
          <span className="mk-seller"><span className="mk-avatar" aria-hidden="true">{(seller || "?").slice(0, 1).toUpperCase()}</span>by {seller}</span>
          <h2 className="mk-title">{project.title}</h2>
          {project.summary ? <p className="mk-summary">{project.summary}</p> : null}
          {project.technologies.length > 0 && (
            <ul className="chips mk-techs-list" aria-label="Technologies">
              {project.technologies.slice(0, 4).map((t) => <li key={t.slug} className="chip">{t.name}</li>)}
            </ul>
          )}
          <span className="mk-prices">
            {project.offers.length === 0 ? <span className="mp-price">No files yet</span> : project.offers.map((o) => <PriceTag key={o.kind} offer={o} />)}
          </span>
        </span>
      </Link>
    </li>
  );
}