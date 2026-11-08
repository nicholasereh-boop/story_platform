// Loads YouTube's IFrame Player API once and shares it. Every ResourceBoard player that is watched by the
// VideoPlaybackCoordinator (story embeds, marketplace previews, Academy lessons) goes through this one loader, so the
// script is requested a single time per page.
let loading = null;

export function loadYouTubeApi() {
  if (typeof window === "undefined") return Promise.reject(new Error("no window"));
  if (window.YT?.Player) return Promise.resolve(window.YT);
  if (loading) return loading;
  loading = new Promise((resolve, reject) => {
    const previous = window.onYouTubeIframeAPIReady;
    window.onYouTubeIframeAPIReady = () => {
      previous?.();
      resolve(window.YT);
    };
    const script = document.createElement("script");
    script.src = "https://www.youtube.com/iframe_api";
    script.async = true;
    script.onerror = () => { loading = null; reject(new Error("The YouTube player could not be loaded.")); };
    document.head.appendChild(script);
  });
  return loading;
}
