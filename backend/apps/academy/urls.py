"""Academy routes, all under /api/v1/academy/ (docs/ARCHITECTURE.md). Each phase adds its own group of paths below."""
from django.urls import path

from . import views_authoring, views_core, views_learning, views_paid

urlpatterns = [
    path("academy/config/", views_core.AcademyConfigView.as_view(), name="academy-config"),
    # Phase 2: staff authoring (every view checks is_staff on the server)
    path("academy/admin/courses/", views_authoring.AdminCourseListCreateView.as_view(), name="academy-admin-courses"),
    path("academy/admin/courses/<int:pk>/", views_authoring.AdminCourseDetailView.as_view(), name="academy-admin-course"),
    path("academy/admin/courses/<int:pk>/lessons/", views_authoring.AdminLessonListCreateView.as_view(), name="academy-admin-lessons"),
    path("academy/admin/courses/<int:pk>/lessons/reorder/", views_authoring.AdminLessonReorderView.as_view(), name="academy-admin-reorder"),
    path("academy/admin/courses/<int:pk>/access/", views_paid.AdminCourseAccessView.as_view(), name="academy-admin-access"),
    path("academy/admin/courses/<int:pk>/<slug:action>/", views_authoring.AdminCourseStatusView.as_view(), name="academy-admin-course-status"),
    path("academy/admin/lessons/<int:pk>/", views_authoring.AdminLessonDetailView.as_view(), name="academy-admin-lesson"),
    # Phase 3: free learning (public catalog and lessons, saved progress, lesson comments)
    path("academy/courses/", views_learning.CourseListView.as_view(), name="academy-courses"),
    path("academy/courses/<slug:slug>/", views_learning.CourseDetailView.as_view(), name="academy-course"),
    path("academy/courses/<slug:slug>/enroll/", views_learning.EnrollView.as_view(), name="academy-enroll"),
    path("academy/lessons/<int:pk>/", views_learning.LessonDetailView.as_view(), name="academy-lesson"),
    path("academy/lessons/<int:pk>/access/", views_learning.LessonAccessView.as_view(), name="academy-lesson-access"),
    path("academy/lessons/<int:pk>/progress/", views_learning.LessonProgressView.as_view(), name="academy-lesson-progress"),
    path("academy/lessons/<int:pk>/comments/", views_learning.LessonCommentsView.as_view(), name="academy-lesson-comments"),
    path("academy/comments/<int:pk>/", views_learning.OwnCommentView.as_view(), name="academy-comment"),
    path("academy/my-learning/", views_learning.MyLearningView.as_view(), name="academy-my-learning"),
    # Phase 4: paid courses (checkout, verification, webhook, orders) and staff tools for orders and complimentary access
    path("academy/courses/<int:pk>/checkout/", views_paid.CourseCheckoutView.as_view(), name="academy-checkout"),
    path("academy/payments/verify/", views_paid.VerifyPaymentView.as_view(), name="academy-payment-verify"),
    path("academy/payments/webhook/", views_paid.PaymentWebhookView.as_view(), name="academy-payment-webhook"),
    path("academy/orders/", views_paid.MyOrdersView.as_view(), name="academy-orders"),
    path("academy/admin/orders/", views_paid.AdminOrderListView.as_view(), name="academy-admin-orders"),
    path("academy/admin/orders/<int:pk>/refund/", views_paid.AdminRefundView.as_view(), name="academy-admin-refund"),
]