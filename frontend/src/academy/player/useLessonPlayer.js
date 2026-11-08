import { useEffect, useRef, useState } from "react";
import { loadYouTubeApi } from "./youtubeApi";
import { coordinator } from "../../player/VideoPlaybackCoordinator";

// Controls one lesson's YouTube player and reports progress to the server. The browser only REPORTS: it adds up the seconds the
// video was really playing and sends position / watched / duration every `intervalSeconds`, on pause, at the end, and when the
// learner leaves. The server decides what counts (it limits how fast watch time can grow) and when the lesson is complete.
//
// onReport({ position_seconds, watched_seconds, duration_seconds }) is called by this hook; it should send them to the server.
export function useLessonPlayer({ videoId, startSeconds = 0, baselineWatched = 0, intervalSeconds = 15, enabled = true, onReport }) {
  const host = useRef(null);
  const [status, setStatus] = useState("loading"); // loading | ready | error
  const report = useRef(onReport);
  report.current = onReport;

  useEffect(() => {
    if (!enabled || !videoId || !host.current) return undefined;
    let cancelled = false;
    let player = null;
    let unregister = null; // stops the shared one-video-at-a-time coordinator from touching this player
    const playerId = coordinator.createId("lesson");
    let tick = null;
    let watched = baselineWatched; // whole seconds the video has been playing, including earlier visits
    let sinceReport = 0;

    const snapshot = () => {
      let position = 0;
      let duration = 0;
      try { position = Math.floor(player?.getCurrentTime?.() || 0); duration = Math.floor(player?.getDuration?.() || 0); } catch { /* player gone */ }
      return { position_seconds: position, watched_seconds: Math.floor(watched), duration_seconds: duration };
    };
    const send = () => { sinceReport = 0; report.current?.(snapshot()); };
    const stopTick = () => { if (tick) { clearInterval(tick); tick = null; } };
    const startTick = () => {
      if (tick) return;
      tick = setInterval(() => {
        watched += 1; sinceReport += 1;
        if (sinceReport >= intervalSeconds) send();
      }, 1000);
    };

    loadYouTubeApi()
      .then((YT) => {
        if (cancelled || !host.current) return;
        const mount = document.createElement("div");
        host.current.appendChild(mount);
        player = new YT.Player(mount, {
          host: "https://www.youtube-nocookie.com",
          videoId,
          width: "100%",
          height: "100%",
          playerVars: { rel: 0, modestbranding: 1, playsinline: 1, start: Math.max(0, Math.floor(startSeconds)), origin: window.location.origin },
          events: {
            onReady: () => { if (!cancelled) setStatus("ready"); },
            onError: () => { if (!cancelled) setStatus("error"); },
            onStateChange: (e) => {
              const s = e.data;
              if (s === YT.PlayerState.PLAYING) { coordinator.notifyPlaying(playerId); startTick(); }
              else {
                stopTick();
                if (s === YT.PlayerState.PAUSED || s === YT.PlayerState.ENDED) { coordinator.notifyStopped(playerId); send(); }
              }
            },
          },
        });
        // Pausing here (when another video starts) fires a PAUSED event, so the watch time is still saved by send() above.
        unregister = coordinator.register(playerId, { pause: () => { try { player?.pauseVideo?.(); } catch { /* player gone */ } } });
      })
      .catch(() => { if (!cancelled) setStatus("error"); });

    const onHidden = () => { if (document.visibilityState === "hidden" && watched > baselineWatched) send(); };
    document.addEventListener("visibilitychange", onHidden);

    return () => {
      cancelled = true;
      document.removeEventListener("visibilitychange", onHidden);
      unregister?.();
      stopTick();
      if (player && watched > baselineWatched) send();
      try { player?.destroy?.(); } catch { /* already gone */ }
      host.current?.replaceChildren?.(); // clear the player container (no HTML is ever parsed here)
    };
    // The player is rebuilt only when the lesson (video) changes, never because progress numbers moved.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [videoId, enabled]);

  return { host, status };
}
