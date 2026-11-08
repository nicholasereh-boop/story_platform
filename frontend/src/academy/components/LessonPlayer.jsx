import { useQuery } from "@tanstack/react-query";
import { getAcademyConfig } from "../api/academy";
import { saveProgress } from "../api/learning";
import { useLessonPlayer } from "../player/useLessonPlayer";

// The video for one lesson. It is only mounted when the server has said the learner may watch (and sent the video id).
export default function LessonPlayer({ lesson, progress, onSaved }) {
  const config = useQuery({ queryKey: ["ac-config"], queryFn: getAcademyConfig, staleTime: 5 * 60 * 1000 });
  const { host, status } = useLessonPlayer({
    videoId: lesson.youtube_id,
    startSeconds: progress?.position_seconds || 0,
    baselineWatched: progress?.watched_seconds || 0,
    intervalSeconds: config.data?.progress_update_interval_seconds || 15,
    enabled: Boolean(lesson.youtube_id),
    onReport: (snapshot) => saveProgress(lesson.id, snapshot).then((r) => onSaved?.(r)).catch(() => {}),
  });
  return (
    <div className="ac-player">
      <div className="ac-player-frame" ref={host} />
      {status === "loading" && <p className="ac-player-note" role="status">Loading the video…</p>}
      {status === "error" && (
        <p className="ac-player-note ac-error" role="alert">
          The video could not be loaded. Check your connection and refresh. <a href={`https://www.youtube.com/watch?v=${lesson.youtube_id}`} target="_blank" rel="noopener noreferrer">Watch on YouTube</a>
        </p>
      )}
    </div>
  );
}