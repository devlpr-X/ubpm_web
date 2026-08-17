"""Google Sign-In — ID token шалгах, хэрэглэгч холбох.

Вэб болон мобайл апп хоёулаа энэ модулийг ашиглана. Аюулгүй байдлын шалгалт
(`verify_google_id_token`) нэг газар байснаар хоёр урсгал хооронд зөрөх
эрсдэлгүй.

Хоёр урсгал ID token авах арга нь л ялгаатай:

* **Апп** — төхөөрөмж дээрх native цонхноос ID token-ыг шууд авч POST-лоно.
* **Вэб** — сонгодог authorization-code redirect: хуудсыг бүхэлд нь Google руу
  явуулж, буцаж ирэхэд `code`-г `id_token`-оор солино. iframe, popup, гуравдагч
  талын cookie ашигладаггүй тул браузерын тохиргооноос хамаарахгүй.
"""

import secrets
from urllib.parse import urlencode

import requests
from django.conf import settings
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from .models import User

GOOGLE_AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
# Хэрэглэгчийг таних хамгийн бага хүрээ. Илүү scope нэмбэл Google-ийн
# баталгаажуулалт (verification) шаардаж эхэлдэг.
GOOGLE_SCOPES = "openid email profile"


class GoogleAuthError(Exception):
    """Токен хүчингүй эсвэл тохиргоо дутуу. Дуудагч тал өөрийн хэлбэрээр буцаана."""


def web_login_configured():
    """Вэбийн redirect урсгалд client ID болон secret хоёулаа хэрэгтэй."""
    return bool(settings.GOOGLE_OAUTH_WEB_CLIENT_ID and settings.GOOGLE_OAUTH2_SECRET)


def build_authorization_url(redirect_uri, state, nonce):
    """Хэрэглэгчийг явуулах Google-ийн зөвшөөрлийн хаяг."""
    params = {
        "client_id": settings.GOOGLE_OAUTH_WEB_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": GOOGLE_SCOPES,
        "state": state,
        "nonce": nonce,
        # Олон бүртгэлтэй хүнд сонголт өгнө; эс бөгөөс сүүлд нэвтэрснээр нь шууд орно.
        "prompt": "select_account",
        "access_type": "online",
    }
    return f"{GOOGLE_AUTH_URI}?{urlencode(params)}"


def exchange_code_for_id_token(code, redirect_uri):
    """Google-ийн буцаасан `code`-г `id_token`-оор солино.

    `redirect_uri` нь эхний хүсэлтийнхтэй ЯГ ижил байх ёстой — Google үүнийг
    тэмдэгт тэмдэгтээр тулгадаг.
    """
    if not web_login_configured():
        raise GoogleAuthError("Google нэвтрэлт серверт тохируулагдаагүй байна.")

    try:
        res = requests.post(
            GOOGLE_TOKEN_URI,
            data={
                "code": code,
                "client_id": settings.GOOGLE_OAUTH_WEB_CLIENT_ID,
                "client_secret": settings.GOOGLE_OAUTH2_SECRET,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=10,
        )
    except requests.RequestException:
        raise GoogleAuthError("Google-тэй холбогдож чадсангүй. Дахин оролдоно уу.") from None

    if res.status_code != 200:
        # Ихэвчлэн redirect_uri таарахгүй эсвэл secret буруу үед.
        raise GoogleAuthError("Google-ийн зөвшөөрлийг баталгаажуулж чадсангүй.")

    id_token = (res.json() or {}).get("id_token")
    if not id_token:
        raise GoogleAuthError("Google id_token буцаасангүй.")
    return id_token


def new_state_and_nonce():
    """CSRF-ээс хамгаалах `state` ба токен давтахаас сэргийлэх `nonce`."""
    return secrets.token_urlsafe(32), secrets.token_urlsafe(32)


def verify_google_id_token(token):
    """ID token-ийг шалгаад Google-ийн payload-ыг буцаана.

    Алдаа гарвал `GoogleAuthError`-ыг хэрэглэгчид харуулах мессежтэй шиднэ.
    """
    allowed = settings.GOOGLE_OAUTH_CLIENT_IDS
    if not allowed:
        raise GoogleAuthError("Google нэвтрэлт серверт тохируулагдаагүй байна.")

    try:
        # audience=None: гарын үсэг / issuer / хугацааг шалгаад, `aud`-г доор
        # өөрсдөө шалгана (олон client ID зөвшөөрөгддөг тул).
        info = google_id_token.verify_oauth2_token(token, google_requests.Request())
    except ValueError:
        raise GoogleAuthError("Google token хүчингүй байна.") from None

    if info.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise GoogleAuthError("Google token-ийн эх сурвалж буруу байна.")
    if info.get("aud") not in allowed:
        raise GoogleAuthError("Google token энэ аппад зориулагдаагүй байна.")
    if not (info.get("email") or "").strip() or not info.get("email_verified"):
        raise GoogleAuthError("Google бүртгэлийн email баталгаажаагүй байна.")

    return info


def get_or_create_google_user(info):
    """Payload-оос хэрэглэгчийг олно; байхгүй бол CUSTOMER эрхээр үүсгэнэ.

    Тухайн email-тэй бүртгэл аль хэдийн байвал шинээр үүсгэхгүй, түүн рүү нь
    холбоно — нэг хүн хоёр бүртгэлтэй болохгүй.
    """
    email = info["email"].lower().strip()
    user, created = User.objects.get_or_create(
        email=email,
        defaults={"full_name": info.get("name", ""), "role": User.Role.CUSTOMER},
    )
    if created:
        # Google-ээр бүртгүүлсэн хүнд нууц үг байхгүй; нууц үг сэргээхээр
        # дамжуулан PIN тавьж, дараа нь энгийнээр ч нэвтэрч болно.
        user.set_unusable_password()
        user.save(update_fields=["password"])
    return user, created
