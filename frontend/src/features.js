// Feature switches for the extension features (docs/extension road map/). All are ON unless switched off at build time:
//   VITE_FEATURE_MARKETPLACE=false   VITE_FEATURE_VIDEO_TOOLS=false   VITE_FEATURE_ACADEMY=false
// When off, the routes and navigation links simply do not exist (visitors get the normal 404). The backend has its own
// matching switches (MARKETPLACE_ENABLED, VIDEO_TOOLS_ENABLED, ACADEMY_ENABLED), which are the real control.
const on = (value) => String(value ?? "true").trim().toLowerCase() !== "false";
// News is opt-in: it stays hidden until VITE_FEATURE_NEWS=true is set at build time (the backend has NEWS_ENABLED / NEWS_PUBLIC_ENABLED).
const optIn = (value) => String(value ?? "false").trim().toLowerCase() === "true";

export const FEATURES = {
  marketplace: on(import.meta.env?.VITE_FEATURE_MARKETPLACE),
  videoTools: on(import.meta.env?.VITE_FEATURE_VIDEO_TOOLS),
  academy: on(import.meta.env?.VITE_FEATURE_ACADEMY),
};
// Kept out of FEATURES on purpose so that object keeps its original shape.
export const FEATURE_NEWS = optIn(import.meta.env?.VITE_FEATURE_NEWS);

// Appended to the public header's navigation.
export const EXTENSION_NAV_LINKS = [
  ...(FEATURES.marketplace ? [{ to: "/marketplace", label: "Marketplace" }] : []),
  ...(FEATURES.videoTools ? [{ to: "/video-tools", label: "Video tools" }] : []),
  ...(FEATURES.academy ? [{ to: "/academy", label: "Academy" }] : []),
  ...(FEATURE_NEWS ? [{ to: "/news", label: "News" }] : []),
];

// Appended to the admin sidebar.
export const ADMIN_EXTENSION_LINKS = [
  ...(FEATURES.marketplace ? [{ to: "/admin/marketplace", label: "Marketplace" }] : []),
  ...(FEATURE_NEWS ? [{ to: "/admin/news", label: "News" }] : []),
];