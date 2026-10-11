"""Local development. Uses PostgreSQL when configured, SQLite only if no DB variables are set."""
from .base import *  # noqa: F401,F403

DEBUG = True
# A throwaway key so a fresh checkout starts; production refuses to start without a real one.
SECRET_KEY = SECRET_KEY or "dev-only-insecure-key-do-not-use-in-production-0123456789"  # noqa: F405

if not DATABASES:  # noqa: F405  (no DATABASE_URL / DB_NAME given)
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}  # noqa: F405

# Verification and password-reset emails are printed in the terminal running the server.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
