from django.urls import path

from . import views as v

urlpatterns = [
    path("auth/csrf/", v.CsrfView.as_view(), name="auth-csrf"),
    path("auth/providers/", v.ProvidersView.as_view(), name="auth-providers"),
    path("auth/register/", v.RegisterView.as_view(), name="auth-register"),
    path("auth/login/", v.LoginView.as_view(), name="auth-login"),
    path("auth/logout/", v.LogoutView.as_view(), name="auth-logout"),
    path("auth/me/", v.MeView.as_view(), name="auth-me"),
    path("auth/email/verify/", v.EmailVerifyView.as_view(), name="auth-email-verify"),
    path("auth/email/resend/", v.EmailResendView.as_view(), name="auth-email-resend"),
    path("auth/password/reset/", v.PasswordResetRequestView.as_view(), name="auth-password-reset"),
    path("auth/password/reset/confirm/", v.PasswordResetConfirmView.as_view(), name="auth-password-reset-confirm"),
]
