// Routes for the two extension features, kept in one place so App.jsx only needs to spread them in.
// Each group is empty when its feature flag is off (see features.js), and then those addresses simply get the public 404.
import RequireLogin from "./auth/RequireLogin";
import { FEATURES } from "./features";
import MarketplaceReviewPage from "./pages/admin/MarketplaceReviewPage";
import EditProjectPage from "./pages/marketplace/EditProjectPage";
import MarketplacePage from "./pages/marketplace/MarketplacePage";
import MyProjectsPage from "./pages/marketplace/MyProjectsPage";
import ProjectDetailPage from "./pages/marketplace/ProjectDetailPage";
import PurchasesPage from "./pages/marketplace/PurchasesPage";
import VideoDownloaderPage from "./pages/video/VideoDownloaderPage";
import { adminNewsRoutes, publicNewsRoutes } from "./features/news/routes";

const signedIn = (element, message) => <RequireLogin message={message}>{element}</RequireLogin>;

// Inside the public layout (header + footer).
export const publicExtensionRoutes = [
  ...(FEATURES.marketplace
    ? [
        { path: "/marketplace", element: <MarketplacePage /> },
        { path: "/marketplace/projects/:slug", element: <ProjectDetailPage /> },
        { path: "/marketplace/publish", element: signedIn(<EditProjectPage />, "Log in to sell your source code.") },
        { path: "/marketplace/projects/:id/edit", element: signedIn(<EditProjectPage />) },
        { path: "/marketplace/my", element: signedIn(<MyProjectsPage />) },
        { path: "/marketplace/purchases", element: signedIn(<PurchasesPage />, "Log in to see your purchases.") },
      ]
    : []),
  ...(FEATURES.videoTools ? [{ path: "/video-tools", element: <VideoDownloaderPage /> }] : []),
  ...publicNewsRoutes, // News (empty unless VITE_FEATURE_NEWS=true)
];

// Inside /admin (staff only: the parent route already requires staff).
export const adminExtensionRoutes = [
  ...(FEATURES.marketplace ? [{ path: "marketplace", element: <MarketplaceReviewPage /> }] : []),
  ...adminNewsRoutes, // News newsroom (empty unless VITE_FEATURE_NEWS=true)
];