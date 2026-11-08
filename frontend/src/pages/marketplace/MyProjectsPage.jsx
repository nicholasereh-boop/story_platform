import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { myProjects } from "../../api/marketplace";
import Pagination from "../../components/Pagination";
import QueryState from "../../components/public/QueryState";
import { ProjectStatus } from "../../components/marketplace/shared";
import { useDocumentMeta } from "../../hooks/useDocumentMeta";
import { useState } from "react";
import "./marketplace.css";

export default function MyProjectsPage() {
  useDocumentMeta({ title: "My projects", robots: "noindex" });
  const [page, setPage] = useState(1);
  const query = useQuery({ queryKey: ["mp-my", "list", page], queryFn: () => myProjects({ page }), placeholderData: (p) => p });
  return (
    <div className="container">
      <div className="mp-head">
        <h1>My projects</h1>
        <div className="row">
          <Link className="btn secondary" to="/marketplace/purchases">My purchases</Link>
          <Link className="btn" to="/marketplace/publish">New project</Link>
        </div>
      </div>
      <QueryState query={query} skeleton={<p className="muted">Loading…</p>} isEmpty={(d) => d.items.length === 0}
        empty={<div className="empty"><p>You have not added a project yet. <Link to="/marketplace/publish">Sell your first one.</Link></p></div>}>
        {(data) => (
          <>
            <div className="table-wrap">
              <table className="table">
                <caption className="sr-only">Your projects</caption>
                <thead><tr><th scope="col">Project</th><th scope="col">Status</th><th scope="col">Files</th><th scope="col"><span className="sr-only">Actions</span></th></tr></thead>
                <tbody>
                  {data.items.map((p) => (
                    <tr key={p.id}>
                      <th scope="row">{p.title}</th>
                      <td><ProjectStatus status={p.status} /></td>
                      <td>{p.offers.length === 0 ? "None" : p.offers.map((o) => o.kind).join(" + ")}</td>
                      <td><Link to={`/marketplace/projects/${p.id}/edit`}>Edit<span className="sr-only"> {p.title}</span></Link></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination pagination={data.pagination} onPage={setPage} />
          </>
        )}
      </QueryState>
    </div>
  );
}
