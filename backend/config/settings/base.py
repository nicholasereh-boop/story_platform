"""Settings shared by every environment.

Everything that differs between machines (secrets, hosts, database, Redis, URLs)
is read from environment variables, loaded from backend/.env by python-dotenv.
"""
import os
from pathlib import Path
from urllib.parse import unquote, urlparse

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def env_list(name, default=""):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


# --- Core ------------------------------------------------------------------
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")  # development.py/production.py decide what to do if empty
DEBUG = False
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173").rstrip("/")
SITE_NAME = os.environ.get("SITE_NAME", "StoryBoard")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",  # required by django-allauth
    # third party
    "rest_framework",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    # project apps (empty skeletons until later phases)
    "apps.core",
    "apps.accounts",
    "apps.stories",
    "apps.comments",
    "apps.reactions",
    "apps.media",
    "apps.analytics",
    "apps.audit",
    # extension roadmap: additive apps
    "apps.source_marketplace",
    "apps.video_tools",
    "apps.academy",
    "apps.news"
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "apps.core.security.SecurityHeadersMiddleware",  # Permissions-Policy + Content-Security-Policy (Phase 10)
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",  # must come before CommonMiddleware
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.accounts.middleware.SessionActivityMiddleware",  # staff idle timeout + session registry (Phase 10)
    "apps.accounts.middleware.DjangoAdminMfaMiddleware",  # the built-in admin obeys the two-step rule too (Phase 10)
    "django.contrib.messages.middleware.MessageMiddleware",
    "allauth.account.middleware.AccountMiddleware",  # must come after MessageMiddleware
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]


# --- Database (PostgreSQL) ---------------------------------------------------
def postgres_from_env():
    """Return a PostgreSQL config from DATABASE_URL or DB_* variables, or None if neither is set."""
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        parsed = urlparse(url)
        if parsed.scheme not in ("postgres", "postgresql"):
            raise ImproperlyConfigured("DATABASE_URL must start with postgresql://")
        name, user, password = parsed.path.lstrip("/"), unquote(parsed.username or ""), unquote(parsed.password or "")
        host, port = parsed.hostname or "localhost", parsed.port or 5432
    elif os.environ.get("DB_NAME"):
        name = os.environ["DB_NAME"]
        user = os.environ.get("DB_USER", "")
        password = os.environ.get("DB_PASSWORD", "")
        host = os.environ.get("DB_HOST", "localhost")
        port = os.environ.get("DB_PORT", "5432")
    else:
        return None
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": name,
        "USER": user,
        "PASSWORD": password,
        "HOST": host,
        "PORT": port,
        "CONN_MAX_AGE": 60,
    }


_postgres = postgres_from_env()
DATABASES = {"default": _postgres} if _postgres else {}  # development.py may add a SQLite fallback
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Redis: cache + Celery broker ---------------------------------------------
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
    }
}
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TASK_SERIALIZER = "json"

# --- Passwords & i18n -----------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# --- Static & media (development defaults; object storage comes in a later phase) --
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# --- Cookies, CSRF, CORS -----------------------------------------------------------
SESSION_COOKIE_HTTPONLY = True  # JavaScript can never read the session
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"  # the CSRF cookie stays readable by JS so React can send X-CSRFToken
CSRF_COOKIE_HTTPONLY = False  # deliberate: React reads it and sends it back in the X-CSRFToken header
CSRF_TRUSTED_ORIGINS = [FRONTEND_URL]
CORS_ALLOWED_ORIGINS = [FRONTEND_URL]  # ONLY the frontend may call the API from a browser
CORS_ALLOW_CREDENTIALS = True

def _rate(scope, default):
    """Throttle rate for a scope; override with THROTTLE_<SCOPE> (e.g. THROTTLE_LOGIN=20/min)."""
    return os.environ.get(f"THROTTLE_{scope.upper()}", default)


# --- Django REST Framework -----------------------------------------------------------
REST_FRAMEWORK = {
    # Session auth that ALSO demands the CSRF token on anonymous unsafe requests (login, sign-up, password reset),
    # which plain SessionAuthentication skips. See apps/core/authentication.py.
    "DEFAULT_AUTHENTICATION_CLASSES": ["apps.core.authentication.StrictSessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticatedOrReadOnly"],
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardPagination",
    "PAGE_SIZE": 12,
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.URLPathVersioning",
    "DEFAULT_VERSION": "v1",
    "ALLOWED_VERSIONS": ["v1"],
    "DEFAULT_RENDERER_CLASSES": ["apps.core.renderers.EnvelopeRenderer"],
    "EXCEPTION_HANDLER": "apps.core.exceptions.api_exception_handler",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",  # views opt in with throttle_scope = "..."
        "apps.core.throttles.AdminWriteThrottle",  # staff writes only (Phase 10)
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": _rate("anon", "100/hour"),
        "user": _rate("user", "1000/hour"),
        "login": _rate("login", "10/min"),
        "register": _rate("register", "10/hour"),
        "password_reset": _rate("password_reset", "5/hour"),
        "profile_update": _rate("profile_update", "30/hour"),
        "media_upload": _rate("media_upload", "60/hour"),
        "public_read": _rate("public_read", "120/min"),  # the public website's read API, per IP
        "like": _rate("like", "60/min"),  # like / unlike, per user (Phase 8)
        "like_anonymous": _rate("like_anonymous", "60/hour"),  # like / unlike by visitors without an account, per IP
        "academy_progress": _rate("academy_progress", "900/hour"),  # saving lesson progress, per user (the player saves every ~15 seconds)
        "academy_comment": _rate("academy_comment", "30/hour"),  # posting lesson comments, per user
        "academy_enroll": _rate("academy_enroll", "60/hour"),  # starting a free course, per user
        "academy_checkout": _rate("academy_checkout", "30/hour"),  # starting a course payment, per user
        "academy_verify": _rate("academy_verify", "120/hour"),  # checking a payment after returning from Paystack, per user
        "academy_webhook": _rate("academy_webhook", "600/hour"),  # Paystack's webhook calls, per IP
        "comment": _rate("comment", "10/hour"),  # posting comments, per user (Phase 8)
        "report": _rate("report", "20/hour"),  # reporting comments, per user (Phase 8)
        "analytics": _rate("analytics", "120/min"),  # page-view events, per IP (Phase 9)
        # --- Phase 10 ---
        "logout": _rate("logout", "60/min"),
        "password_change": _rate("password_change", "10/hour"),  # per user
        "admin_write": _rate("admin_write", "300/min"),  # writes by one staff user
        "mfa": _rate("mfa", "10/10min"),  # two-step verification attempts, per user
        "data_export": _rate("data_export", "3/hour"),  # "download my data", per user
        "account_delete": _rate("account_delete", "3/hour"),  # per user
        "csp_report": _rate("csp_report", "30/min"),  # browser CSP reports, per IP
        "news_takedown": _rate("news_takedown", "5/hour"),  # the public copyright-complaint form, per IPS
        "news_comment": _rate("news_comment", "20/hour"),  # posting news comments, per user
        "news_search": _rate("news_search", "30/min"),  # searching news, per IP
        "news_counter": _rate("news_counter", "60/min"),  # the licence page-view counter, per IP
    },
    # How many reverse proxies (e.g. Nginx) sit in front of Django. 0 = trust REMOTE_ADDR only.
    # Set NUM_PROXIES=1 behind one proxy, otherwise every visitor shares the proxy's IP in throttles.
    "NUM_PROXIES": int(os.environ.get("NUM_PROXIES", "0")),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Story Publishing API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": r"/api/v[0-9]",
}


# --- Accounts & authentication (Phase 3) ---------------------------------------------
AUTH_USER_MODEL = "accounts.User"
SITE_ID = 1
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14  # 14 days

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",  # used by our /auth/login/ API
    "allauth.account.auth_backends.AuthenticationBackend",  # needed by allauth's Google flow
]

# Failed-login lockout (apps/accounts/throttling.py): per email + IP.
LOGIN_MAX_FAILURES = 5
LOGIN_FAILURE_WINDOW_SECONDS = 15 * 60

# django-allauth (v65+ setting names). Email-only accounts. Email addresses are never verified.
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_USER_MODEL_EMAIL_FIELD = "email"
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_EMAIL_SUBJECT_PREFIX = f"[{SITE_NAME}] "
ACCOUNT_ADAPTER = "apps.accounts.adapters.AccountAdapter"

SOCIALACCOUNT_ADAPTER = "apps.accounts.adapters.SocialAccountAdapter"
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_LOGIN_ON_GET = False  # starting Google login needs a POST (with CSRF token)
# Link a Google login to an existing account with the same email. Safe ONLY because allauth
# does this only when the provider says the email is verified, which Google does.
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        # Credentials come from the environment, so no SocialApp rows are needed in the database.
        "APP": {
            "client_id": os.environ.get("GOOGLE_CLIENT_ID", ""),
            "secret": os.environ.get("GOOGLE_CLIENT_SECRET", ""),
            "key": "",
        },
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
    }
}
LOGIN_URL = f"{FRONTEND_URL}/login"
LOGIN_REDIRECT_URL = FRONTEND_URL  # where allauth sends the browser after a Google login
ACCOUNT_LOGOUT_REDIRECT_URL = FRONTEND_URL

DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "no-reply@localhost")


# --- Media (Phase 5) ---------------------------------------------------------------
MEDIA_MAX_UPLOAD_BYTES = int(os.environ.get("MEDIA_MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))  # per file
MEDIA_MAX_FILES_PER_REQUEST = 10


def storages_from_env(environ=None):
    """Django STORAGES setting. Local disk by default; S3-compatible object storage when a bucket is configured.

    Works for AWS S3, Cloudflare R2, MinIO and DigitalOcean Spaces. Nothing here touches the network,
    and every variable may be empty without crashing startup.
    """
    environ = os.environ if environ is None else environ
    storages = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
    bucket = (environ.get("MEDIA_STORAGE_BUCKET") or "").strip()
    if bucket:
        endpoint = (environ.get("MEDIA_STORAGE_ENDPOINT") or "").strip() or None
        storages["default"] = {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "bucket_name": bucket,
                "region_name": (environ.get("MEDIA_STORAGE_REGION") or "").strip() or None,
                "access_key": (environ.get("MEDIA_STORAGE_ACCESS_KEY") or "").strip() or None,
                "secret_key": (environ.get("MEDIA_STORAGE_SECRET_KEY") or "").strip() or None,
                "endpoint_url": endpoint,
                "custom_domain": (environ.get("MEDIA_CDN_DOMAIN") or "").strip() or None,
                "addressing_style": "path" if endpoint else None,  # MinIO / R2 style URLs
                "file_overwrite": False,  # never replace an existing object
                "querystring_auth": False,  # public URLs without signatures
                "default_acl": None,  # access is controlled by the bucket policy
                # Filenames are unique uuids, so browsers and CDNs may cache them forever.
                "object_parameters": {"CacheControl": "public, max-age=31536000, immutable"},
            },
        }
    return storages


STORAGES = storages_from_env()


# --- Reader engagement (Phase 8) ----------------------------------------------------
# How long after posting a reader may still edit their own comment.
COMMENT_EDIT_WINDOW_MINUTES = int(os.environ.get("COMMENT_EDIT_WINDOW_MINUTES", "15"))
# Comma-separated words that make the spam filter reject a comment (whole words, case-insensitive).
COMMENT_BLOCKED_WORDS = [w.strip().lower() for w in os.environ.get("COMMENT_BLOCKED_WORDS", "").split(",") if w.strip()]


# --- Analytics (Phase 9) -------------------------------------------------------------
# Master switch: false = the collect endpoint accepts and ignores every event.
ANALYTICS_ENABLED = os.environ.get("ANALYTICS_ENABLED", "true").strip().lower() not in ("0", "false", "no", "off")
# The same visitor viewing the same page again within this many minutes is not counted again.
ANALYTICS_DEDUPE_MINUTES = int(os.environ.get("ANALYTICS_DEDUPE_MINUTES", "30"))
# Raw page-view events are deleted after this many days (aggregates are kept). Never less than 35 (see docs/ANALYTICS.md).
ANALYTICS_RETENTION_DAYS = int(os.environ.get("ANALYTICS_RETENTION_DAYS", "90"))
# Secret used to hash visitor and session ids. Empty = derived from DJANGO_SECRET_KEY.
ANALYTICS_HASH_SECRET = os.environ.get("ANALYTICS_HASH_SECRET", "")


# --- Security and privacy (Phase 10) --------------------------------------------------
# Header settings read by Django's SecurityMiddleware and by apps/core/security.py.
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin-allow-popups"  # "same-origin" would break the Google login popup
X_FRAME_OPTIONS = "DENY"
# true = browsers only REPORT Content-Security-Policy violations (use while rolling out a stricter policy).
CSP_REPORT_ONLY = env_bool("CSP_REPORT_ONLY", False)

# One-time links: password reset 1 hour.
PASSWORD_RESET_TIMEOUT = 60 * 60

# The built-in Django admin lives at a path of your choice and can be switched off (recommended in production).
DJANGO_ADMIN_URL = os.environ.get("DJANGO_ADMIN_URL", "django-admin/").strip().strip("/") + "/"
DJANGO_ADMIN_ENABLED = env_bool("DJANGO_ADMIN_ENABLED", True)

# Staff sessions end after this many minutes without a request. Everyone else keeps SESSION_COOKIE_AGE.
STAFF_SESSION_IDLE_MINUTES = int(os.environ.get("STAFF_SESSION_IDLE_MINUTES", "120"))

# Two-step verification (TOTP) for staff. Off = optional (staff who set it up are still checked).
STAFF_MFA_REQUIRED = env_bool("STAFF_MFA_REQUIRED", False)
MFA_ENCRYPTION_KEY = os.environ.get("MFA_ENCRYPTION_KEY", "")  # empty = derived from DJANGO_SECRET_KEY
MFA_ISSUER = os.environ.get("MFA_ISSUER", SITE_NAME)  # the name an authenticator app shows

# Audit log (apps/audit): entries older than this are removed by `manage.py purge_audit_logs` (minimum 30 days).
AUDIT_RETENTION_DAYS = int(os.environ.get("AUDIT_RETENTION_DAYS", "365"))
AUDIT_HASH_SECRET = os.environ.get("AUDIT_HASH_SECRET", "")  # keys the IP hash; empty = derived from DJANGO_SECRET_KEY

# Uploads: at most this many files per user per hour, on top of the per-request throttle.
MEDIA_UPLOAD_QUOTA_PER_HOUR = int(os.environ.get("MEDIA_UPLOAD_QUOTA_PER_HOUR", "100"))

# Privacy: what the policy page and the consent banner say. Nothing here is a secret.
PRIVACY_CONSENT_MODE = os.environ.get("PRIVACY_CONSENT_MODE", "notice").strip().lower()
if PRIVACY_CONSENT_MODE not in ("notice", "opt_in", "opt_out"):
    raise ImproperlyConfigured("PRIVACY_CONSENT_MODE must be notice, opt_in or opt_out.")
SITE_OPERATOR_NAME = os.environ.get("SITE_OPERATOR_NAME", SITE_NAME)
SITE_CONTACT_EMAIL = os.environ.get("SITE_CONTACT_EMAIL", "")
PRIVACY_POLICY_DATE = os.environ.get("PRIVACY_POLICY_DATE", "")  # YYYY-MM-DD, the date the owner approved the text

# Logging: every handler redacts passwords, tokens, session ids, cookies and e-mail addresses (apps/core/redaction.py).
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"redact": {"()": "apps.core.redaction.RedactingFilter"}},
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain", "filters": ["redact"]}},
    "root": {"handlers": ["console"], "level": os.environ.get("LOG_LEVEL", "INFO")},
}


# --- Source code marketplace (extension roadmap, Phase 2) -----------------------------------------------
# Everything below is new. Master switch: false = every marketplace endpoint answers 404.
MARKETPLACE_ENABLED = env_bool("MARKETPLACE_ENABLED", True)
# true = a seller's project (and later changes to a published one) waits for staff approval before buyers see it.
MARKETPLACE_REQUIRE_REVIEW = env_bool("MARKETPLACE_REQUIRE_REVIEW", True)
MARKETPLACE_CURRENCY = os.environ.get("MARKETPLACE_CURRENCY", "USD").strip().upper()[:3] or "USD"  # prices and Paystack charges are in US dollars
MARKETPLACE_MAX_PRICE = int(os.environ.get("MARKETPLACE_MAX_PRICE", "10000"))  # highest price per package, major units (USD)
# Backend source code is never free: a buyer must pay (verified by Paystack) before the download starts.
MARKETPLACE_BACKEND_REQUIRES_PAYMENT = env_bool("MARKETPLACE_BACKEND_REQUIRES_PAYMENT", True)# Source packages are stored OUTSIDE MEDIA_ROOT and have no URL: only the authorised download endpoint serves them.
# Prices are shown in MARKETPLACE_CURRENCY (USD); Paystack charges the equivalent in MARKETPLACE_CHARGE_CURRENCY (the currency your
# Paystack account collects, naira by default) and settles to you in naira. The buyer's card is billed in their own currency by their bank.
MARKETPLACE_CHARGE_CURRENCY = os.environ.get("MARKETPLACE_CHARGE_CURRENCY", "NGN").strip().upper()[:3] or "NGN"
MARKETPLACE_FX_LIVE = env_bool("MARKETPLACE_FX_LIVE", True)  # look the dollar rate up live (cached for an hour)
MARKETPLACE_FX_RATE = os.environ.get("MARKETPLACE_FX_RATE", "").strip()  # fallback: how many naira one dollar is, e.g. 1500
MARKETPLACE_FX_URL = os.environ.get("MARKETPLACE_FX_URL", "https://open.er-api.com/v6/latest").strip()
MARKETPLACE_FX_TIMEOUT = int(os.environ.get("MARKETPLACE_FX_TIMEOUT", "5"))
MARKETPLACE_PRIVATE_ROOT = os.environ.get("MARKETPLACE_PRIVATE_ROOT") or str(BASE_DIR / "private_media" / "marketplace")
MARKETPLACE_MAX_ARCHIVE_BYTES = int(os.environ.get("MARKETPLACE_MAX_ARCHIVE_BYTES", str(50 * 1024 * 1024)))  # uploaded / imported ZIP
MARKETPLACE_MAX_UNPACKED_BYTES = int(os.environ.get("MARKETPLACE_MAX_UNPACKED_BYTES", str(300 * 1024 * 1024)))  # archive-bomb guard
MARKETPLACE_MAX_FILE_BYTES = int(os.environ.get("MARKETPLACE_MAX_FILE_BYTES", str(50 * 1024 * 1024)))  # one file inside
MARKETPLACE_MAX_FILES = int(os.environ.get("MARKETPLACE_MAX_FILES", "5000"))
MARKETPLACE_GITHUB_ENABLED = env_bool("MARKETPLACE_GITHUB_ENABLED", True)
MARKETPLACE_GITHUB_TIMEOUT = int(os.environ.get("MARKETPLACE_GITHUB_TIMEOUT", "30"))  # seconds, per request to GitHub
# Paystack. The secret key lives ONLY here (server environment), never in the frontend. Empty = payments are off and
# checkout answers "not available"; free packages keep working.
PAYSTACK_SECRET_KEY = os.environ.get("PAYSTACK_SECRET_KEY", "").strip()
PAYSTACK_API_BASE = os.environ.get("PAYSTACK_API_BASE", "https://api.paystack.co").strip().rstrip("/")
PAYSTACK_TIMEOUT = int(os.environ.get("PAYSTACK_TIMEOUT", "20"))
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"].update({
    "marketplace_read": _rate("marketplace_read", "120/min"),  # public browsing, per IP
    "marketplace_write": _rate("marketplace_write", "120/hour"),  # editing / submitting, per user
    "marketplace_upload": _rate("marketplace_upload", "20/hour"),  # ZIP uploads, GitHub imports, screenshots, per user
    "marketplace_checkout": _rate("marketplace_checkout", "20/hour"),  # starting a payment, per user
    "marketplace_verify": _rate("marketplace_verify", "60/hour"),  # confirming a payment, per user
    "marketplace_download": _rate("marketplace_download", "60/hour"),  # package downloads, per user
    "marketplace_webhook": _rate("marketplace_webhook", "300/min"),  # Paystack callbacks, per IP
})


# --- Video tools (extension roadmap, Phase 3) -------------------------------------------------------------
# Master switch: false = every video-tools endpoint answers 404.
VIDEO_TOOLS_ENABLED = env_bool("VIDEO_TOOLS_ENABLED", True)
# Reviewed, permitted download methods, one adapter class per provider, e.g. VIDEO_TOOLS_ADAPTERS=youtube=my_pkg.mod.Adapter
# Empty (the default) = every provider is inspect-only. A provider also has to be switched on by staff in the Django admin
# (Video tools > Provider capabilities) after its current terms were reviewed. See docs/VIDEO_TOOLS.md.
VIDEO_TOOLS_ADAPTERS = dict(
    item.split("=", 1) for item in env_list("VIDEO_TOOLS_ADAPTERS") if "=" in item
)
VIDEO_TOOLS_PRIVATE_ROOT = os.environ.get("VIDEO_TOOLS_PRIVATE_ROOT") or str(BASE_DIR / "private_media" / "video_tools")
VIDEO_TOOLS_MAX_FILE_BYTES = int(os.environ.get("VIDEO_TOOLS_MAX_FILE_BYTES", str(200 * 1024 * 1024)))
VIDEO_TOOLS_RETENTION_HOURS = int(os.environ.get("VIDEO_TOOLS_RETENTION_HOURS", "24"))  # how long a finished file is kept
VIDEO_TOOLS_JOB_RETENTION_DAYS = int(os.environ.get("VIDEO_TOOLS_JOB_RETENTION_DAYS", "30"))  # then the job record is deleted too
VIDEO_TOOLS_MAX_ACTIVE_JOBS = int(os.environ.get("VIDEO_TOOLS_MAX_ACTIVE_JOBS", "2"))  # per person, at the same time
VIDEO_TOOLS_MAX_JOBS_PER_DAY = int(os.environ.get("VIDEO_TOOLS_MAX_JOBS_PER_DAY", "20"))  # per person
VIDEO_TOOLS_TIMEOUT_SECONDS = int(os.environ.get("VIDEO_TOOLS_TIMEOUT_SECONDS", "300"))
VIDEO_TOOLS_RUN_INLINE = env_bool("VIDEO_TOOLS_RUN_INLINE", False)  # true = run jobs inside the request (no Celery); development only
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"].update({
    "video_inspect": _rate("video_inspect", "60/min"),  # link checks, per IP
    "video_download": _rate("video_download", "10/hour"),  # download requests, per user
    "video_poll": _rate("video_poll", "180/min"),  # status checks and file fetches, per user
})





# --- Academy (extension roadmap): free and paid courses, lessons, progress, lesson comments ----------------
# Everything below is new. Master switch: false = every Academy endpoint answers 404 (the rest of the site is unaffected).
ACADEMY_ENABLED = env_bool("ACADEMY_ENABLED", True)
ACADEMY_CURRENCY = os.environ.get("ACADEMY_CURRENCY", "USD").strip().upper()[:3] or "USD"  # course prices are shown in this currency
ACADEMY_MAX_PRICE = int(os.environ.get("ACADEMY_MAX_PRICE", "10000"))  # highest course price, major units
ACADEMY_DEFAULT_COMPLETION_THRESHOLD = int(os.environ.get("ACADEMY_DEFAULT_COMPLETION_THRESHOLD", "90"))  # percent of a video that counts as watched
ACADEMY_PROGRESS_UPDATE_INTERVAL_SECONDS = int(os.environ.get("ACADEMY_PROGRESS_UPDATE_INTERVAL_SECONDS", "15"))  # how often the player saves progress
ACADEMY_COMMENT_GATE_DEFAULT = env_bool("ACADEMY_COMMENT_GATE_DEFAULT", True)  # new lessons start with "comment to unlock the next lesson" on
ACADEMY_COMMENT_MODERATION = env_bool("ACADEMY_COMMENT_MODERATION", False)  # true: new lesson comments wait for staff approval
ACADEMY_PAYMENT_PROVIDER = os.environ.get("ACADEMY_PAYMENT_PROVIDER", "paystack").strip().lower()  # only "paystack" is implemented



# extension roadmap: News (rights-based news section). Everything is off-switchable without touching the rest of the site.
NEWS_ENABLED = env_bool("NEWS_ENABLED", True)  # false: every /news/ endpoint answers 404
NEWS_PUBLIC_ENABLED = env_bool("NEWS_PUBLIC_ENABLED", False)  # false: News is staff-only (staging); turn on after acceptance checks
NEWS_IMPORT_ENABLED = env_bool("NEWS_IMPORT_ENABLED", False)  # false: no feed is ever fetched, only manual entry works
NEWS_REQUIRE_COMMERCIAL_RIGHTS = env_bool("NEWS_REQUIRE_COMMERCIAL_RIGHTS", True)  # the site shows ads: articles need explicit commercial-use rights to go live
NEWS_PUBLIC_CACHE_SECONDS = int(os.environ.get("NEWS_PUBLIC_CACHE_SECONDS", "60"))  # how long public lists are cached (a version key clears them on every change)
NEWS_COPYRIGHT_CONTACT = os.environ.get("NEWS_COPYRIGHT_CONTACT", "")
NEWS_TAKEDOWN_NOTIFY_EMAIL = os.environ.get("NEWS_TAKEDOWN_NOTIFY_EMAIL", "")

NEWS_FEED_TIMEOUT_SECONDS = int(os.environ.get("NEWS_FEED_TIMEOUT_SECONDS", "10"))  # per request when polling a feed
NEWS_FEED_MAX_BYTES = int(os.environ.get("NEWS_FEED_MAX_BYTES", str(2 * 1024 * 1024)))  # largest feed document accepted

NEWS_COMMENTS_ENABLED = env_bool("NEWS_COMMENTS_ENABLED", False)  # false: no News comments (reading or writing); turn on after moderation is ready
NEWS_COMMENT_MODERATION = env_bool("NEWS_COMMENT_MODERATION", False)  # true: new News comments wait for staff approval
NEWS_RIGHTS_WARNING_DAYS = int(os.environ.get("NEWS_RIGHTS_WARNING_DAYS", "14"))  # monitoring warns when a rights record ends within this many days