// The loader now lives in src/player/ because story embeds and marketplace previews share it with the Academy.
// This re-export keeps the Academy's existing import path working unchanged.
export { loadYouTubeApi } from "../../player/youtubeApi";
