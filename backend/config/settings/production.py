"""Production. Strict: needs a real secret key and PostgreSQL, and forces HTTPS-only cookies."""
import os

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403

if not SECRET_KEY:  # noqa: F405
    raise ImproperlyConfigured("Set DJANGO_SECRET_KEY.")
if not DATABASES:  # noqa: F405
    raise ImproperlyConfigured("Set DATABASE_URL (or DB_NAME/DB_USER/DB_PASSWORD/DB_HOST/DB_PORT).")

DEBUG = False
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = env_bool("DJANGO_SSL_REDIRECT", True)  # noqa: F405
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")  # when behind Nginx
SECURE_HSTS_SECONDS = 31536000
SECURE_CONTENT_TYPE_NOSNIFF = True

# Email (verification + password reset). Never log message bodies: they contain one-time links.
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)  # noqa: F405
