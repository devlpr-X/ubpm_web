"""Production settings — strict, SMTP email, secure cookies."""

from .base import *  # noqa: F401, F403
from .base import env

DEBUG = False

# Hosts. Defaults are permissive so the app boots on a fresh PaaS deploy;
# tighten via the ALLOWED_HOSTS env var once the final domain is known.
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["*"])

# Railway injects RAILWAY_PUBLIC_DOMAIN — trust it automatically for CSRF.
RAILWAY_DOMAIN = env("RAILWAY_PUBLIC_DOMAIN", default="")
CSRF_TRUSTED_ORIGINS = env.list(
    "CSRF_TRUSTED_ORIGINS",
    default=["https://*.up.railway.app", "https://*.railway.app"],
)
if RAILWAY_DOMAIN:
    if RAILWAY_DOMAIN not in ALLOWED_HOSTS and "*" not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(RAILWAY_DOMAIN)
    CSRF_TRUSTED_ORIGINS.append(f"https://{RAILWAY_DOMAIN}")

# Email — SMTP when credentials are provided, otherwise fall back to console
# so a deploy without email configured still boots and runs.
EMAIL_HOST = env("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
if EMAIL_HOST_USER and EMAIL_HOST_PASSWORD:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
# SMTP порт хаалттай/удаан үед холболт мөнхөд унжихаас сэргийлнэ (секунд).
EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT", default=10)

# Email доторх линкүүд localhost руу заахгүйн тулд Railway domain-ийг ашиглана.
SITE_URL = env("SITE_URL", default=f"https://{RAILWAY_DOMAIN}" if RAILWAY_DOMAIN else "")

# Security. SSL redirect is on by default but can be disabled via env if the
# platform's health check hits the container over plain HTTP.
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30  # 30 days
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
X_FRAME_OPTIONS = "DENY"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "WARNING"},
}
