import { useQuery } from "@tanstack/react-query";
import { getRelatedStories } from "../../api/public";
import StoryGrid, { StoryGridSkeleton } from "./StoryGrid";

// "Keep reading": up to 4 related stories. This section is a bonus, so a failure just hides it.
export default function RelatedStories({ slug }) {
  const query = useQuery({ queryKey: ["public", "related", slug], queryFn: () => getRelatedStories(slug) });
  if (query.isError || (query.data && query.data.length === 0)) return null;
  return (
    <section className="related" aria-labelledby="related-heading">
      <h2 id="related-heading">Keep reading</h2>
      {query.isLoading ? <StoryGridSkeleton count={4} /> : <StoryGrid stories={query.data} />}
    </section>
  );
}
