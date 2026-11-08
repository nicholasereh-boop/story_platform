import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { listProjects, listTechnologies } from "../../api/marketplace";
import Pagination from "../../components/Pagination";
import QueryState from "../../components/public/QueryState";
import MarketCard from "../../components/market/MarketCard";
import TechFlow from "../../components/market/TechFlow";
import { useDocumentMeta } from "../../hooks/useDocumentMeta";
import "./marketplace.css";
import "../../styles/market-pages.css";

export default function MarketplacePage() {
  const [params, setParams] = useSearchParams();
  const q = params.get("q") || "";
  const tech = params.get("tech") || "";
  const free = params.get("free") === "1";
  const page = Math.max(1, Number(params.get("page")) || 1);
  useDocumentMeta({ title: "Source code marketplace", description: "Browse ready-made website source code: frontends and backends you can download or buy." });

  const techs = useQuery({ queryKey: ["mp-techs"], queryFn: listTechnologies, staleTime: 5 * 60 * 1000 });
  const projects = useQuery({
    queryKey: ["mp-projects", { q, tech, free, page }],
    queryFn: () => listProjects({ q: q || undefined, tech: tech || undefined, free: free ? 1 : undefined, page }),
    placeholderData: (previous) => previous,
  });

  const set = (key, value) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value); else next.delete(key);
    next.delete("page");
    setParams(next);
  };

  const total = projects.data?.pagination?.count;

  return (
    <div className="container mk-page">
      <header className="mk-hero">
        <span className="mk-orb mk-orb-a" aria-hidden="true" />
        <span className="mk-orb mk-orb-b" aria-hidden="true" />
        <p className="mk-eyebrow">Ready-made · Pay once · Own the code</p>
        <h1>Source code marketplace</h1>
        <p className="mk-sub">Ready-made frontends and backends from other builders.</p>
        <ul className="mk-perks" aria-label="Why buy here">
          <li>⚡ Skip weeks of building</li>
          <li>🧩 Frontend &amp; backend</li>
          <li>🔒 Secure Paystack checkout</li>
        </ul>
        {Number.isFinite(total) && total > 0 ? <p className="mk-count"><strong>{total}</strong> {total === 1 ? "project" : "projects"} ready to download</p> : null}
        {/* <Link className="btn" to="/marketplace/publish">Sell your source code</Link> */}
      </header>

      <TechFlow techs={techs.data} />
      {tech ? (
        <p className="mk-active" role="status">Showing projects made with <strong>{tech}</strong> <button type="button" onClick={() => set("tech", "")}>Clear ✕</button></p>
      ) : null}
{/* 
      <form className="mp-filters" role="search" aria-label="Filter projects" onSubmit={(e) => e.preventDefault()}>
        <div className="field">
          <label htmlFor="mp-q">Search</label>
          <input id="mp-q" type="search" value={q} onChange={(e) => set("q", e.target.value)} placeholder="Shop, blog, dashboard…" />
        </div>
        <div className="field">
          <label htmlFor="mp-tech">Technology</label>
          <select id="mp-tech" value={tech} onChange={(e) => set("tech", e.target.value)}>
            <option value="">All technologies</option>
            {(techs.data || []).map((t) => <option key={t.slug} value={t.slug}>{t.name}</option>)}
          </select>
        </div>
        <label className="check">
          <input type="checkbox" checked={free} onChange={(e) => set("free", e.target.checked ? "1" : "")} /> Free only
        </label>
      </form> */}

      <QueryState
        query={projects}
        skeleton={<p className="muted">Loading projects…</p>}
        isEmpty={(d) => d.items.length === 0}
        empty={<div className="empty"><p>No projects match. Try clearing a filter, or be the first to <Link to="/marketplace/publish">share one</Link>.</p></div>}
      >
        {(data) => (
          <>
            <ul className="mk-grid">{data.items.map((p, i) => <MarketCard key={p.id} project={p} variant={i === 0 && page === 1 ? "feature" : "card"} />)}</ul>
            <Pagination pagination={data.pagination} onPage={(n) => { const next = new URLSearchParams(params); next.set("page", String(n)); setParams(next); window.scrollTo?.(0, 0); }} />
          </>
        )}
      </QueryState>
    </div>
  );
}