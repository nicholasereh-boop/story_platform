import { useEffect } from "react";
import { coordinator } from "./VideoPlaybackCoordinator";
import { loadYouTubeApi } from "./youtubeApi";

// Puts an EXISTING YouTube <iframe> (one React already renders, whose address has enablejsapi=1) under the
// VideoPlaybackCoordinator. The iframe markup and the content that produced it are not changed at all: this only watches
// the player and pauses it when another one starts.
//
// Why the iframe is NOT destroyed on cleanup: YT.Player.destroy() removes the iframe from the page, but React owns that
// element and removes it itself. Unregistering from the coordinator and ignoring later events is enough, and nothing is
// left behind that can pause or report for a player that is no longer on the page.
export function useCoordinatedYoutubeIframe(iframeRef, { enabled = true, videoId = "", idPrefix = "embed" } = {}) {
  useEffect(() => {
    const iframe = iframeRef.current;
    if (!enabled || !iframe) return undefined;
    const id = coordinator.createId(idPrefix);
    let disposed = false;
    let ready = false;
    let pausePending = false;
    let player = null;
    let unregister = null;

    const pauseNow = () => { try { player?.pauseVideo?.(); } catch { /* player gone */ } };
    const pause = () => {
      if (!player) return;
      // A player that is not ready yet cannot be paused; remember to do it the moment it is, so it never starts by itself later.
      if (!ready) { pausePending = true; return; }
      pauseNow();
    };

    loadYouTubeApi()
      .then((YT) => {
        if (disposed || !iframeRef.current) return;
        const PLAYING = YT.PlayerState?.PLAYING ?? 1;
        const PAUSED = YT.PlayerState?.PAUSED ?? 2;
        const ENDED = YT.PlayerState?.ENDED ?? 0;
        player = new YT.Player(iframe, {
          events: {
            onReady: () => {
              if (disposed) return;
              ready = true;
              if (pausePending) { pausePending = false; pauseNow(); return; }
              // An autoplaying embed may already be playing before the API attached; announce it so others pause.
              let state = null;
              try { state = player?.getPlayerState?.(); } catch { /* ignore */ }
              if (state === PLAYING) coordinator.notifyPlaying(id);
            },
            onStateChange: (event) => {
              if (disposed) return;
              ready = true;
              if (event.data === PLAYING) coordinator.notifyPlaying(id);
              else if (event.data === PAUSED || event.data === ENDED) coordinator.notifyStopped(id);
            },
          },
        });
        unregister = coordinator.register(id, { pause });
      })
      .catch(() => { /* the player script could not load: the embed simply works as it always did, uncoordinated */ });

    return () => {
      disposed = true;
      unregister?.();
    };
    // Re-attach only when the video itself changes (React then also gives the iframe a new key).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, videoId]);
}
