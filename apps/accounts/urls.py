from django.urls import path

from . import admin_views as av
from . import views as v

urlpatterns = [
    path("auth/csrf/", v.CsrfView.as_view(), name="auth-csrf"),
    path("auth/providers/", v.ProvidersView.as_view(), name="auth-providers"),
    path("auth/register/", v.RegisterView.as_view(), name="auth-register"),
    path("auth/login/", v.LoginView.as_view(), name="auth-login"),
    path("auth/logout/", v.LogoutView.as_view(), name="auth-logout"),
    path("auth/me/", v.MeView.as_view(), name="auth-me"),
    path("auth/me/export/", v.MeExportView.as_view(), name="auth-me-export"),
    path("auth/password/change/", v.PasswordChangeView.as_view(), name="auth-password-change"),
    path("auth/sessions/", v.SessionListView.as_view(), name="auth-sessions"),
    path("auth/sessions/revoke-all/", v.SessionRevokeAllView.as_view(), name="auth-sessions-revoke-all"),
    path("auth/mfa/status/", v.MfaStatusView.as_view(), name="auth-mfa-status"),
    path("auth/mfa/setup/", v.MfaSetupView.as_view(), name="auth-mfa-setup"),
    path("auth/mfa/confirm/", v.MfaConfirmView.as_view(), name="auth-mfa-confirm"),
    path("auth/mfa/verify/", v.MfaVerifyView.as_view(), name="auth-mfa-verify"),
    path("auth/mfa/disable/", v.MfaDisableView.as_view(), name="auth-mfa-disable"),
    path("auth/mfa/recovery-codes/", v.MfaRecoveryCodesView.as_view(), name="auth-mfa-recovery-codes"),
    path("auth/email/verify/", v.EmailVerifyView.as_view(), name="auth-email-verify"),
    path("auth/email/resend/", v.EmailResendView.as_view(), name="auth-email-resend"),
    path("auth/password/reset/", v.PasswordResetRequestView.as_view(), name="auth-password-reset"),
    path("auth/password/reset/confirm/", v.PasswordResetConfirmView.as_view(), name="auth-password-reset-confirm"),
    # staff user management (Phase 10)
    path("admin/users/", av.AdminUserListView.as_view(), name="admin-users"),
    path("admin/users/<int:pk>/", av.AdminUserDetailView.as_view(), name="admin-user"),
    path("admin/users/<int:pk>/revoke-sessions/", av.AdminUserRevokeSessionsView.as_view(), name="admin-user-revoke-sessions"),
    path("admin/users/<int:pk>/resend-verification/", av.AdminUserResendVerificationView.as_view(), name="admin-user-resend-verification"),
]
