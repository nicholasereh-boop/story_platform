import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { listProjects } from "../../api/marketplace";
import MarketCard from "./MarketCard";

// A row of other projects under a project page. A bonus: when there are none (or it cannot load) it is simply not shown.
export default function MoreProjects({ excludeId }) {
  const query = useQuery({
    queryKey: ["mp-more-projects"],
    queryFn: async () => (await listProjects({ page_size: 10 })) ?? { items: [] },
    staleTime: 60 * 1000,
    retry: false,
  });
  const items = (query.data?.items || []).filter((p) => p.id !== excludeId).slice(0, 8);
  if (items.length === 0) return null;
  return (
    <section className="mk-more" aria-labelledby="mk-more-h">
      <div className="mk-more-head">
        <h2 id="mk-more-h">More source code</h2>
        <Link to="/marketplace">See all →</Link>
      </div>
      <ul className="mk-rail">{items.map((p) => <MarketCard key={p.id} project={p} variant="compact" />)}</ul>
    </section>
  );
}