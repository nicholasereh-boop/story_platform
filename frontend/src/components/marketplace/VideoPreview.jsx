import { useRef } from "react";
import { youtubeEmbedUrl } from "../../utils/youtube";
import { useCoordinatedYoutubeIframe } from "../../player/useCoordinatedYoutubePlayer";

// The seller's demo video. Only an 11-character id ever reaches the iframe address (the server stores nothing else),
// the player is the privacy-friendly youtube-nocookie one, and it never autoplays.
export default function VideoPreview({ id, title, label = "Demo video", showHeading = false }) {
  const frame = useRef(null);
  const valid = /^[A-Za-z0-9_-]{11}$/.test(id || "");
  // Watched by the shared video coordinator: starting any other ResourceBoard or Academy video pauses this one.
  useCoordinatedYoutubeIframe(frame, { enabled: valid, videoId: id || "", idPrefix: "preview" });
  if (!valid) return null;
  return (
    <section aria-label={label} className="yt-embed">
      {showHeading ? <h3>{label}</h3> : null}
      <iframe
        key={id}
        ref={frame}
        src={youtubeEmbedUrl(id, { jsApi: true })}
        title={`${label}: ${title}`}
        allow="accelerometer; encrypted-media; gyroscope; picture-in-picture"
        allowFullScreen
        loading="lazy"
        referrerPolicy="strict-origin-when-cross-origin"
      />
    </section>
  );
}
