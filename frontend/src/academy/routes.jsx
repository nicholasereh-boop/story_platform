// The Academy's routes, kept in one place so App.jsx only needs to spread them in. Empty when the feature flag is off
// (see features.js), and then every /academy address simply gets the normal public 404.
import RequireLogin from "../auth/RequireLogin";
import RequireStaff from "../auth/RequireStaff";
import { FEATURES } from "../features";
import AcademyLayout from "./components/AcademyLayout";
import AcademyAdminPage from "./pages/AcademyAdminPage";
import AcademyOrdersAdminPage from "./pages/AcademyOrdersAdminPage";
import AcademyHomePage from "./pages/AcademyHomePage";
import CourseCatalogPage from "./pages/CourseCatalogPage";
import CourseDetailPage from "./pages/CourseDetailPage";
import CourseEditorPage from "./pages/CourseEditorPage";
import LessonPage from "./pages/LessonPage";
import MyLearningPage from "./pages/MyLearningPage";
import MyOrdersPage from "./pages/MyOrdersPage";

function AcademyNotFound() {
  return (
    <div className="ac-container">
      <h1 className="ac-h2">Page not found</h1>
      <p className="ac-lede">That Academy page does not exist.</p>
    </div>
  );
}

// A top-level route group with its own layout (not inside the public site frame).
export const academyRoutes = FEATURES.academy
  ? [
      {
        path: "/academy",
        element: <AcademyLayout />,
        children: [
          { index: true, element: <AcademyHomePage /> },
          // Catalog and courses (public: the server decides what each visitor may open)
          { path: "free", element: <CourseCatalogPage access="free" /> },
          { path: "paid", element: <CourseCatalogPage access="paid" /> },
          { path: "free/courses/:slug", element: <CourseDetailPage kind="free" /> },
          { path: "paid/courses/:slug", element: <CourseDetailPage kind="paid" /> },
          { path: "learn/:lessonId", element: <LessonPage /> },
          { path: "my-learning", element: <RequireLogin><MyLearningPage /></RequireLogin> },
          { path: "orders", element: <RequireLogin><MyOrdersPage /></RequireLogin> },
          // Staff only (the server checks too; this just shows the right screen)
          { path: "admin", element: <RequireStaff><AcademyAdminPage /></RequireStaff> },
          { path: "admin/orders", element: <RequireStaff><AcademyOrdersAdminPage /></RequireStaff> },
          { path: "admin/courses/new", element: <RequireStaff><CourseEditorPage /></RequireStaff> },
          { path: "admin/courses/:id", element: <RequireStaff><CourseEditorPage /></RequireStaff> },
          { path: "*", element: <AcademyNotFound /> },
        ],
      },
    ]
  : [];