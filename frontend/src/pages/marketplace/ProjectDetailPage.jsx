import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { getProject } from "../../api/marketplace";
import MoreProjects from "../../components/market/MoreProjects";
import PackageActions from "../../components/marketplace/PackageActions";
import ProjectGallery from "../../components/marketplace/ProjectGallery";
import VideoPreview from "../../components/marketplace/VideoPreview";
import { ProjectStatus } from "../../components/marketplace/shared";
import QueryState from "../../components/public/QueryState";
import PublicNotFound from "../public/PublicNotFound";
import { useDocumentMeta } from "../../hooks/useDocumentMeta";
import "./marketplace.css";
import "../../styles/market-pages.css";

function Detail({ project }) {
  const live = project.status === "published";
  useDocumentMeta({
    title: project.title,
    description: project.summary || project.description.slice(0, 160),
    robots: live ? "index,follow" : "noindex",
  });
  const hasVideo = Boolean(project.youtube_id || project.frontend_video_id || project.backend_video_id);
  const hasPaid = project.offers.some((o) => !o.is_free); // payment wording only appears when something here costs money
  return (
    <div className="container mk-page">
      <p className="mk-crumb"><Link to="/marketplace">← Marketplace</Link></p>
      <header className="mk-detail-head">
        <h1>{project.title}</h1>
        <p className="mk-byline"><span className="mk-avatar" aria-hidden="true">{(project.seller || "?").slice(0, 1).toUpperCase()}</span>by {project.seller}</p>
        {project.technologies.length > 0 && (
          <ul className="chips" aria-label="Technologies">{project.technologies.map((t) => <li key={t.slug} className="chip">{t.name}</li>)}</ul>
        )}
      </header>
      {project.viewer?.is_owner && (
        <div className="notice" role="status">
          <p>This is your project. Status: <ProjectStatus status={project.status} />{" "}
            <Link to={`/marketplace/projects/${project.id}/edit`}>Edit</Link></p>
        </div>
      )}
      <div className="mk-detail">
        <div className="mk-main">
          <ProjectGallery screenshots={project.screenshots} title={project.title} />
          {project.summary ? <p className="mk-lede">{project.summary}</p> : null}
          {hasVideo && (
            <div className="mk-videos">
              <VideoPreview id={project.youtube_id} title={project.title} label="Frontend and backend overview video" showHeading />
              <VideoPreview id={project.frontend_video_id} title={project.title} label="Frontend video" showHeading />
              <VideoPreview id={project.backend_video_id} title={project.title} label="Backend video" showHeading />
            </div>
          )}
          <section aria-labelledby="about-h" className="mk-section">
            <h2 id="about-h">About this project</h2>
            <p className="mp-text">{project.description}</p>
          </section>
          {project.notes ? (
            <section aria-labelledby="notes-h" className="mk-section">
              <h2 id="notes-h">Setup and usage notes</h2>
              <p className="mp-text">{project.notes}</p>
            </section>
          ) : null}
        </div>
        <aside aria-label="Get this project" className="mk-buy">
          <div className="mk-buy-head">
            <h2>Get the code</h2>
            <p>{hasPaid ? "Pay once, then download it as a zip." : "Free to download as a zip."}</p>
          </div>
          <PackageActions project={project} />
          <ul className="mk-trust">
            {hasPaid && <li><span aria-hidden="true">🔒</span> Secure checkout with Paystack</li>}
            {hasPaid && <li><span aria-hidden="true">⚡</span> Download unlocks as soon as payment is confirmed</li>}
            <li><span aria-hidden="true">🛡️</span> Files are checked when they are uploaded</li>
          </ul>
          <p className="mp-meta">Downloads are only available to people who are signed in{hasPaid ? ", and paid packages unlock after your payment is confirmed" : ""}.</p>
        </aside>
      </div>
      <MoreProjects excludeId={project.id} />
    </div>
  );
}

export default function ProjectDetailPage() {
  const { slug } = useParams();
  const query = useQuery({ queryKey: ["mp-project", slug], queryFn: () => getProject(slug) });
  return (
    <QueryState query={query} skeleton={<div className="container"><p className="muted">Loading…</p></div>} notFound={<PublicNotFound what="project" />}>
      {(project) => <Detail project={project} />}
    </QueryState>
  );
}