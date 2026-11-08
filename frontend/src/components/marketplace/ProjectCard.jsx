import { Link } from "react-router-dom";
import { PriceTag, safeImageSrc } from "./shared";

export default function ProjectCard({ project }) {
  const src = safeImageSrc(project.cover?.url);
  return (
    <li className="mp-card">
      <Link className="mp-card-link" to={`/marketplace/projects/${project.slug}`}>
        <div className="mp-card-media">
          {src ? <img src={src} alt={project.cover.alt_text || ""} loading="lazy" width={project.cover.width || undefined} height={project.cover.height || undefined} /> : <span aria-hidden="true">No preview</span>}
          {project.has_video ? <span className="mp-badge" aria-label="Has a video">▶ Video</span> : null}
        </div>
        <div className="mp-card-body">
          <h2>{project.title}</h2>
          {project.summary ? <p>{project.summary}</p> : null}
          <p className="mp-meta">by {project.seller}</p>
          {project.technologies.length > 0 && (
            <ul className="chips" aria-label="Technologies">
              {project.technologies.slice(0, 5).map((t) => <li key={t.slug} className="chip">{t.name}</li>)}
            </ul>
          )}
          <div className="mp-prices">
            {project.offers.length === 0 ? <span className="mp-price">No files yet</span> : project.offers.map((o) => <PriceTag key={o.kind} offer={o} />)}
          </div>
        </div>
      </Link>
    </li>
  );
}