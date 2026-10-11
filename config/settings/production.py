"""Production. Strict: needs a real secret key and PostgreSQL, and forces HTTPS-only cookies."""
import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403

from .guards import validate_production

DEBUG = False

# Refuse to start with an unsafe configuration (Phase 10). Every problem is listed at once.
_problems = validate_production(
    secret_key=SECRET_KEY,  # noqa: F405
    debug=DEBUG,
    allowed_hosts=ALLOWED_HOSTS,  # noqa: F405
    allowed_hosts_from_env=bool(os.environ.get("DJANGO_ALLOWED_HOSTS", "").strip()),
    frontend_url=FRONTEND_URL,  # noqa: F405
    cors_origins=CORS_ALLOWED_ORIGINS,  # noqa: F405
    csrf_origins=CSRF_TRUSTED_ORIGINS,  # noqa: F405
    databases=DATABASES,  # noqa: F405
)
if _problems:
    raise ImproperlyConfigured("Unsafe production configuration:\n - " + "\n - ".join(_problems))

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = env_bool("DJANGO_SSL_REDIRECT", True)  # noqa: F405
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")  # when behind Nginx
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
CORS_ALLOW_ALL_ORIGINS = False
SECURE_CONTENT_TYPE_NOSNIFF = True

# Email (verification + password reset). Never log message bodies: they contain one-time links.
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)  # noqa: F405
