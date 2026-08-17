"""Google Sign-In — ID token шалгах, хэрэглэгч холбох.

Вэб (`accounts:google_login`) болон мобайл апп (`api:google`) хоёулаа энэ
модулийг ашиглана. Аюулгүй байдлын шалгалт нэг газар байснаар хоёр урсгал
хооронд зөрөх эрсдэлгүй.

Хоёр урсгал ижил ажилладаг: клиент тал Google-ээс ID token авч сервер рүү
илгээнэ, сервер түүнийг Google-ийн нийтийн түлхүүрээр шалгана. Redirect ч
байхгүй, client secret ч хэрэггүй.
"""

from django.conf import settings
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from .models import User


class GoogleAuthError(Exception):
    """Токен хүчингүй эсвэл тохиргоо дутуу. Дуудагч тал өөрийн хэлбэрээр буцаана."""


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
