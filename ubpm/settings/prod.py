"""Production settings — strict, SMTP email, secure cookies."""

import logging
from email.utils import formataddr, parseaddr

from .base import *  # noqa: F401, F403
from .base import DEFAULT_FROM_EMAIL, env

DEBUG = False

# Hosts. ubpm.mn бол үндсэн домайн; Railway домайн нь fallback тул хамт
# зөвшөөрнө. ALLOWED_HOSTS env var өгвөл эндхийн default-ыг дарна.
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["ubpm.mn", "www.ubpm.mn"])

# Мобайл апп нь ubpm.mn ажиллахгүй үед Railway домайн руу шилждэг (nөөц API хаяг).
# RAILWAY_PUBLIC_DOMAIN нь custom домайныг заадаг болсон тул тэр домайныг доорх
# автомат нэмэлт барьж авахгүй — ".up.railway.app" бүх дэд домайныг зөвшөөрнө.
if not any(h.endswith(".up.railway.app") for h in ALLOWED_HOSTS):
    ALLOWED_HOSTS.append(".up.railway.app")

# Бүх траффик ubpm.mn руу 301-ээр цуглана — www болон Railway домайн хоёулаа.
# ubpm.mn унасан үед CANONICAL_HOST="" болговол Railway домайн нөөц болж эргэнэ.
CANONICAL_HOST = env("CANONICAL_HOST", default="ubpm.mn")

# Railway injects RAILWAY_PUBLIC_DOMAIN — trust it automatically for CSRF.
RAILWAY_DOMAIN = env("RAILWAY_PUBLIC_DOMAIN", default="")
CSRF_TRUSTED_ORIGINS = env.list(
    "CSRF_TRUSTED_ORIGINS",
    default=[
        "https://ubpm.mn",
        "https://www.ubpm.mn",
        "https://*.up.railway.app",
        "https://*.railway.app",
    ],
)
if RAILWAY_DOMAIN:
    if RAILWAY_DOMAIN not in ALLOWED_HOSTS and "*" not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(RAILWAY_DOMAIN)
    CSRF_TRUSTED_ORIGINS.append(f"https://{RAILWAY_DOMAIN}")

# Email — SMTP when credentials are provided, otherwise fall back to console
# so a deploy without email configured still boots and runs.
EMAIL_HOST = env("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
# Gmail app password-ыг Google 4-4 бүлгээр зайтай харуулдаг; хуулж тавихад
# орсон зай/хашилтыг цэвэрлэнэ (SMTP AUTH хоосон зайг тэвчихгүй).
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="").strip().replace(" ", "")

# 465 = implicit SSL, 587 = STARTTLS. Хоёуланг нь зэрэг асаавал Django алдаа
# өгдөг тул портоос хамаарч сонгоод, SSL асаалттай үед TLS-ийг хаана.
EMAIL_USE_SSL = env.bool("EMAIL_USE_SSL", default=EMAIL_PORT == 465)
EMAIL_USE_TLS = False if EMAIL_USE_SSL else env.bool("EMAIL_USE_TLS", default=True)

# Илгээх суваг. Resend (HTTP API) хамгийн түрүүнд — Railway spam-аас сэргийлж
# гадагш SMTP портыг хаадаг тул Gmail SMTP нь "[Errno 101] Network is
# unreachable" гэж унадаг. HTTPS нээлттэй учир API-аар илгээвэл ажиллана.
RESEND_API_KEY = env("RESEND_API_KEY", default="")

if RESEND_API_KEY:
    EMAIL_BACKEND = "apps.notifications.backends.ResendEmailBackend"
elif EMAIL_HOST_USER and EMAIL_HOST_PASSWORD:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
    # Энэ горимд захиа хэнд ч хүрэхгүй, зөвхөн log руу бичигдэнэ. Чимээгүй
    # өнгөрвөл "email явахгүй байна" гэсэн алдаа олоход хэцүү тул сануулна.
    logging.getLogger("ubpm.settings").warning(
        "RESEND_API_KEY ч, EMAIL_HOST_USER/EMAIL_HOST_PASSWORD ч тохируулагдаагүй тул "
        "email нь console backend руу бичигдэнэ — мэдэгдлүүд хэрэглэгчид ХҮРЭХГҮЙ."
    )
# SMTP порт хаалттай/удаан үед холболт мөнхөд унжихаас сэргийлнэ (секунд).
EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT", default=10)

# Gmail SMTP нь нэвтэрсэн бүртгэлээсээ өөр From хаягаар илгээхийг зөвшөөрдөггүй —
# захиаг татгалзах эсвэл From-ыг чимээгүй өөрчилдөг. Тиймээс бүх мэдэгдэл
# (үнийн санал ч мөн адил) үргэлж .env-ийн EMAIL_HOST_USER хаягаас явна;
# DEFAULT_FROM_EMAIL-ээс зөвхөн харагдах нэрийг нь авч үлдээнэ.
#
# Resend-д энэ хамаарахгүй: тэнд From нь баталгаажуулсан домайных (noreply@ubpm.mn)
# байх ёстой бөгөөс Gmail хаяг руу албадан солих нь илгээлтийг эвдэнэ.
if EMAIL_HOST_USER and not RESEND_API_KEY:
    _from_name = parseaddr(DEFAULT_FROM_EMAIL)[0] or "UBPM"
    DEFAULT_FROM_EMAIL = formataddr((_from_name, EMAIL_HOST_USER))
    SERVER_EMAIL = DEFAULT_FROM_EMAIL

# Email доторх линкүүд үндсэн домайн руу заана; ubpm.mn ажиллахгүй үед
# SITE_URL env var-аар Railway domain руу шилжүүлж болно.
SITE_URL = env("SITE_URL", default="https://ubpm.mn")

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
