"""Base settings — shared between dev and prod."""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
)

# Read .env file if present
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY", default="django-insecure-dev-only-do-not-use-in-prod")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "django_filters",
    "crispy_forms",
    "crispy_tailwind",
    "django_htmx",
    "rest_framework",
    "corsheaders",
]

LOCAL_APPS = [
    "apps.accounts",
    "apps.core",
    "apps.branches",
    "apps.intake",
    "apps.quotes",
    "apps.notifications",
    "apps.reports",
    "apps.api",
]

# django_cleanup must come last so its signals see every other app's FileFields.
INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS + ["django_cleanup.apps.CleanupConfig"]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
]

ROOT_URLCONF = "ubpm.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "ubpm.wsgi.application"

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
    ),
}

# Accounts use a simple 4-digit numeric PIN (web + app + API). The default
# Django validators (min length, "too common", "entirely numeric") would all
# reject a 4-digit PIN, so we replace them with a single PIN-format validator.
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "apps.accounts.validators.FourDigitPinValidator"},
]

# How long an emailed password-reset code stays valid (minutes).
PASSWORD_RESET_CODE_TTL_MINUTES = 15

AUTH_USER_MODEL = "accounts.User"

# Email is the login identifier. EmailOrAdminAliasBackend additionally lets an
# operator type the literal username "admin" at the Django admin login.
AUTHENTICATION_BACKENDS = [
    "apps.accounts.backends.EmailOrAdminAliasBackend",
]
# The literal "admin" username resolves to this email (default superuser).
ADMIN_ALIAS_EMAIL = env("ADMIN_ALIAS_EMAIL", default="admin@ubpm.mn")

# TTF font with full Cyrillic coverage, used for PDF/image report exports so
# Mongolian text renders correctly regardless of OS-installed fonts.
REPORT_FONT_REGULAR = BASE_DIR / "static" / "fonts" / "DejaVuSans.ttf"
REPORT_FONT_BOLD = BASE_DIR / "static" / "fonts" / "DejaVuSans-Bold.ttf"

LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

LANGUAGE_CODE = "mn"
TIME_ZONE = "Asia/Ulaanbaatar"
USE_I18N = True
USE_TZ = True

LANGUAGES = [
    ("mn", "Монгол"),
    ("en", "English"),
]
LOCALE_PATHS = [BASE_DIR / "locale"]

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ---------------------------------------------------------------------------
# Storage. By default uploaded media (branch covers, videos, site content) is
# saved to the local MEDIA_ROOT. Set USE_S3=True with S3-compatible credentials
# to push uploads straight to object storage / CDN (AWS S3, Cloudflare R2,
# Bunny, DigitalOcean Spaces, MinIO — all work via the S3 endpoint).
# ---------------------------------------------------------------------------
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

USE_S3 = env.bool("USE_S3", default=False)
if USE_S3:
    AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME")
    # Endpoint for non-AWS providers (R2/Bunny/Spaces/MinIO). Leave blank for AWS.
    AWS_S3_ENDPOINT_URL = env("AWS_S3_ENDPOINT_URL", default=None)
    AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", default=None)
    # Public CDN domain that serves the bucket (e.g. cdn.ubpm.mn). Files are
    # referenced through this domain so delivery goes via the CDN edge.
    AWS_S3_CUSTOM_DOMAIN = env("AWS_S3_CUSTOM_DOMAIN", default=None)
    AWS_QUERYSTRING_AUTH = env.bool("AWS_QUERYSTRING_AUTH", default=False)
    AWS_S3_FILE_OVERWRITE = False
    AWS_DEFAULT_ACL = None
    AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "max-age=31536000, public"}
    STORAGES["default"] = {"BACKEND": "storages.backends.s3.S3Storage"}

# Max upload size for admin-uploaded videos (MB).
MAX_VIDEO_SIZE_MB = env.int("MAX_VIDEO_SIZE_MB", default=200)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# File upload limits — generous, per user requirement
DATA_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024  # 50 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024
MAX_IMAGE_SIZE_MB = 25
MAX_IMAGES_PER_REQUEST = 15

# Crispy
CRISPY_ALLOWED_TEMPLATE_PACKS = "tailwind"
CRISPY_TEMPLATE_PACK = "tailwind"

# Email — overridden per env
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="UBPM <noreply@ubpm.local>")
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# Company contact constants — used in templates and emails
UBPM_PHONES = ["7774-6465", "9915-6465", "8025-6465"]
UBPM_WORKING_HOURS = "10:00–17:30 (амралтын өдөр ч)"

# ---------------------------------------------------------------------------
# REST API (mobile app) — Django REST Framework + JWT
# ---------------------------------------------------------------------------
from datetime import timedelta  # noqa: E402

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_RENDERER_CLASSES": (
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=12),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=30),
    "ROTATE_REFRESH_TOKENS": True,
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# CORS — the Expo app calls from a different origin. Override per env.
CORS_ALLOWED_ORIGINS = env(
    "CORS_ALLOWED_ORIGINS",
    default=[
        "http://localhost:8081",  # Expo dev server (Metro)
        "http://localhost:19006",  # Expo web
    ],
)
CORS_ALLOW_CREDENTIALS = True

# Google Sign-In — accepted OAuth client IDs (the `aud` of the ID token sent by
# the app). Add the Web / iOS / Android client IDs from Google Cloud Console.
GOOGLE_OAUTH_CLIENT_IDS = env("GOOGLE_OAUTH_CLIENT_IDS", default=[])
