"""Development settings — DEBUG on, console email, optional debug toolbar."""

from .base import *  # noqa: F401, F403
from .base import INSTALLED_APPS, MIDDLEWARE, STORAGES, env

DEBUG = True
ALLOWED_HOSTS = ["*"]

# In dev/tests don't use the hashed manifest static storage — it requires a
# collectstatic run and would otherwise raise "Missing staticfiles manifest entry".
STORAGES = {
    **STORAGES,
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Debug toolbar — only when explicitly enabled (avoid pytest noise)
if env.bool("ENABLE_DEBUG_TOOLBAR", default=False):
    INSTALLED_APPS += ["debug_toolbar"]
    MIDDLEWARE = ["debug_toolbar.middleware.DebugToolbarMiddleware", *MIDDLEWARE]
    INTERNAL_IPS = ["127.0.0.1"]

# Verbose logging in dev
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.db.backends": {"level": "WARNING"},
    },
}
