// The News routes, kept in one place so extensionRoutes.jsx only needs to spread them in. Empty when the feature flag is off
// (features.js, VITE_FEATURE_NEWS), and then every /news and /admin/news address gets the normal 404.
import { FEATURE_NEWS } from "../../../features.js";
import CommentsPage from "../pages/CommentsPage";
import ArticleEditorPage from "../pages/ArticleEditorPage";
import ImportPage from "../pages/ImportPage";
import NewsArticlePage from "../pages/NewsArticlePage";
import NewsHomePage from "../pages/NewsHomePage";
import NewsListPage from "../pages/NewsListPage";
import NewsReportPage from "../pages/NewsReportPage";
import NewsroomPage from "../pages/NewsroomPage";
import SourcesPage from "../pages/SourcesPage";
import TakedownsPage from "../pages/TakedownsPage";

// Inside the public layout (site header and footer). Static paths beat /news/:slug in the router, so the order does not matter.
export const buildPublicNewsRoutes = () => [
  { path: "/news", element: <NewsHomePage /> },
  { path: "/news/category/:slug", element: <NewsListPage mode="category" /> },
  { path: "/news/search", element: <NewsListPage mode="search" /> },
  { path: "/news/report", element: <NewsReportPage /> },
  { path: "/news/:slug", element: <NewsArticlePage /> },
];

// Inside /admin (the parent route already requires staff; the server checks again on every call). Paths are relative to /admin.
export const buildAdminNewsRoutes = () => [
  { path: "news", element: <NewsroomPage /> },
  { path: "news/import", element: <ImportPage /> },
  { path: "news/sources", element: <SourcesPage /> },
  { path: "news/takedowns", element: <TakedownsPage /> },
  { path: "news/comments", element: <CommentsPage /> },
  { path: "news/articles/new", element: <ArticleEditorPage /> },
  { path: "news/articles/:id", element: <ArticleEditorPage /> },
];

export const publicNewsRoutes = FEATURE_NEWS ? buildPublicNewsRoutes() : [];
export const adminNewsRoutes = FEATURE_NEWS ? buildAdminNewsRoutes() : [];
