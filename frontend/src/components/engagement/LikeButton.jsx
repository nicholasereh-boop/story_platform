import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../../auth/AuthContext";
import { getLikes, likeStory, unlikeStory } from "../../api/engagement";
import { useSignupPrompt } from "../../engagement/SignupPromptContext";
import { engagementError } from "../../engagement/errors";

// Like / unlike a story.
//  - Optimistic: the heart and count change at once; if the server refuses, they roll back and a message appears.
//  - Disabled while a request is in flight (no double clicks), aria-pressed shows the state, and the count sits in
//    an aria-live region so screen readers hear it change.
//  - Anonymous visitors cannot like: the click opens the signup prompt instead of failing.
export default function LikeButton({ slug, initialCount = 0 }) {
  const { user } = useAuth() || {};
  const { request } = useSignupPrompt();
  const queryClient = useQueryClient();
  const key = ["likes", slug];
  const [error, setError] = useState("");

  // Logged-in readers ask the server whether THEY liked it; for visitors the story's own count is enough.
  const query = useQuery({
    queryKey: key,
    queryFn: () => getLikes(slug),
    enabled: Boolean(user),
    placeholderData: { count: initialCount, liked: false },
    staleTime: 30_000,
  });
  const state = query.data || { count: initialCount, liked: false };

  const mutation = useMutation({
    mutationFn: (wantLiked) => (wantLiked ? likeStory(slug) : unlikeStory(slug)),
    onMutate: async (wantLiked) => {
      await queryClient.cancelQueries({ queryKey: key });
      const previous = state;
      setError("");
      queryClient.setQueryData(key, { liked: wantLiked, count: Math.max(0, previous.count + (wantLiked ? 1 : -1)) });
      return { previous };
    },
    onError: (err, wantLiked, context) => {
      queryClient.setQueryData(key, context?.previous); // roll back
      setError(engagementError(err));
    },
    onSuccess: (result) => queryClient.setQueryData(key, result), // the server's numbers win
  });

  const onClick = () => {
    if (!user) {
      request("like");
      return;
    }
    mutation.mutate(!state.liked);
  };

  return (
    <div className="like-box">
      <button type="button" className={`btn secondary like-btn${state.liked ? " liked" : ""}`} aria-pressed={state.liked} disabled={mutation.isPending} onClick={onClick}>
        <span aria-hidden="true">{state.liked ? "♥" : "♡"}</span> {state.liked ? "Liked" : "Like"}
      </button>
      <span className="like-count" aria-live="polite" aria-atomic="true">
        {state.count} {state.count === 1 ? "like" : "likes"}
      </span>
      {error && <span className="field-error" role="alert">{error}</span>}
    </div>
  );
}
