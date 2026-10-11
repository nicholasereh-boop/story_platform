import { useInfiniteQuery, useQueryClient } from "@tanstack/react-query";
import { createComment, deleteComment, editComment, listComments, reportComment } from "../../api/engagement";
import CommentItem from "./CommentItem";

function CommentsSkeleton() {
  return (
    <div aria-hidden="true">
      {[0, 1, 2].map((i) => (
        <div key={i} className="skeleton line" style={{ height: "3.5rem" }} />
      ))}
    </div>
  );
}

// The discussion under a story: loading / empty / error states, nested replies, "Load more".
// Permissions: buttons come from the server's per-comment flags (can_edit, can_delete), so Edit and Delete only
// ever appear on the reader's own comments (Delete also for staff); Reply needs a verified email, Report a login.
export default function CommentList({ slug, user }) {
  const queryClient = useQueryClient();
  const key = ["comments", slug];
  const query = useInfiniteQuery({
    queryKey: key,
    queryFn: ({ pageParam }) => listComments(slug, pageParam),
    initialPageParam: 1,
    getNextPageParam: (last) => (last.pagination.has_next ? last.pagination.page + 1 : undefined),
  });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: key });
    queryClient.invalidateQueries({ queryKey: ["public", "story", slug] }); // its comment_count changed
  };

  // Each action returns a promise so the item can show its own error message when something is refused.
  const actions = {
    reply: async (parent, text) => {
      await createComment(slug, text, parent.id);
      refresh();
    },
    edit: async (comment, text) => {
      await editComment(comment.id, text);
      refresh();
    },
    remove: async (comment) => {
      await deleteComment(comment.id);
      refresh();
    },
    report: (comment, reason) => reportComment(comment.id, reason),
  };

  if (query.isLoading) return <div role="status" aria-label="Loading comments"><CommentsSkeleton /></div>;
  if (query.isError) {
    return (
      <div className="notice error" role="alert">
        <p>{query.error?.friendly || "Could not load the comments."}</p>
        <button type="button" className="btn secondary small" onClick={() => query.refetch()}>Try again</button>
      </div>
    );
  }

  const comments = query.data.pages.flatMap((page) => page.items);
  if (comments.length === 0) return <p className="empty">No comments yet. Be the first to share your thoughts.</p>;

  return (
    <>
      <ul className="comment-list">
        {comments.map((comment) => (
          <CommentItem key={comment.id} comment={comment} canReply={Boolean(user?.email_verified)} canReport={Boolean(user)} actions={actions} />
        ))}
      </ul>
      {query.isFetchNextPageError && <p className="field-error" role="alert">{query.error?.friendly || "Could not load more comments."}</p>}
      {query.hasNextPage && (
        <button type="button" className="btn secondary" disabled={query.isFetchingNextPage} onClick={() => query.fetchNextPage()}>
          {query.isFetchingNextPage ? "Loading…" : "Load more comments"}
        </button>
      )}
    </>
  );
}
