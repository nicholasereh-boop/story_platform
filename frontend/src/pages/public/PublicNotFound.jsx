import { Link } from "react-router-dom";
import { usePublicMeta } from "../../hooks/usePublicMeta";
import SearchBar from "../../components/public/SearchBar";

export default function PublicNotFound({ what = "page" }) {
  usePublicMeta({ title: "Page not found", robots: "noindex,follow" });
  return (
    <div className="container narrow center">
      <h1>That {what} could not be found</h1>
      <p className="muted">It may have been unpublished or the address may be wrong.</p>
      <SearchBar />
      <p><Link className="btn" to="/stories">Browse all stories</Link></p>
    </div>
  );
}
