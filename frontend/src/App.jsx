import { Navigate, Outlet, createBrowserRouter } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import RequireStaff from "./auth/RequireStaff";
import AdminLayout from "./layouts/AdminLayout";
import PublicLayout from "./layouts/PublicLayout";
import LoginPage from "./pages/LoginPage";
import AccountPage from "./pages/auth/AccountPage";
import ForgotPasswordPage from "./pages/auth/ForgotPasswordPage";
import RegisterPage from "./pages/auth/RegisterPage";
import ResetPasswordPage from "./pages/auth/ResetPasswordPage";
import VerifyEmailPage from "./pages/auth/VerifyEmailPage";
import StoryListPage from "./pages/admin/StoryListPage";
import StoryEditPage from "./pages/admin/StoryEditPage";
import StoryPreviewPage from "./pages/admin/StoryPreviewPage";
import MediaPage from "./pages/admin/MediaPage";
import CommentsPage from "./pages/admin/CommentsPage";
import AnalyticsPage from "./pages/admin/AnalyticsPage";
import AuditLogsPage from "./pages/admin/AuditLogsPage";
import UsersPage from "./pages/admin/UsersPage";
import HomePage from "./pages/public/HomePage";
import PrivacyPage from "./pages/public/PrivacyPage";
import PublicNotFound from "./pages/public/PublicNotFound";
import SearchPage from "./pages/public/SearchPage";
import StoriesPage from "./pages/public/StoriesPage";
import StoryPage from "./pages/public/StoryPage";
import { CategoriesPage, CategoryPage, TagPage, TagsPage } from "./pages/public/TermsPages";

// The root route wraps everything in AuthProvider (public pages use it for the header menu, likes and comments). A "data router" (createBrowserRouter) is used because the
// story editor needs useBlocker() to warn about unsaved changes when leaving the page.
function Root() {
  return (
    <AuthProvider>
      <Outlet />
    </AuthProvider>
  );
}

// Exported separately so tests can build a memory router from the same routes.
export const routes = [
  {
    element: <Root />,
    children: [
      // Account pages for everybody (readers and staff): standalone cards without the site header.
      { path: "/login", element: <LoginPage /> },
      { path: "/register", element: <RegisterPage /> },
      { path: "/forgot-password", element: <ForgotPasswordPage /> },
      { path: "/reset-password", element: <ResetPasswordPage /> },
      { path: "/verify-email", element: <VerifyEmailPage /> },
      {
        path: "/admin",
        element: (
          <RequireStaff>
            <AdminLayout />
          </RequireStaff>
        ),
        children: [
          { index: true, element: <Navigate to="/admin/stories" replace /> },
          { path: "stories", element: <StoryListPage /> },
          { path: "stories/new", element: <StoryEditPage /> },
          { path: "stories/:id/edit", element: <StoryEditPage /> },
          { path: "stories/:id/preview", element: <StoryPreviewPage /> },
          { path: "media", element: <MediaPage /> },
          { path: "comments", element: <CommentsPage /> },
          { path: "analytics", element: <AnalyticsPage /> },
          { path: "users", element: <UsersPage /> },
          { path: "audit-logs", element: <AuditLogsPage /> },
        ],
      },
      // The public website. Everything that is not /login or /admin lands here (unknown addresses get the public 404).
      {
        element: <PublicLayout />,
        children: [
          { path: "/", element: <HomePage /> },
          { path: "/stories", element: <StoriesPage /> },
          { path: "/stories/:slug", element: <StoryPage /> },
          { path: "/categories", element: <CategoriesPage /> },
          { path: "/categories/:slug", element: <CategoryPage /> },
          { path: "/tags", element: <TagsPage /> },
          { path: "/tags/:slug", element: <TagPage /> },
          { path: "/search", element: <SearchPage /> },
          { path: "/privacy", element: <PrivacyPage /> },
          { path: "/account", element: <AccountPage /> },
          { path: "*", element: <PublicNotFound /> },
        ],
      },
    ],
  },
];

export const router = createBrowserRouter(routes);
