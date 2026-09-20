"""Authentication backends for UBPM.

The project uses email as the login identifier. To make the Django admin
convenient, we let an operator type the literal username ``admin`` (instead of
the full email) at the admin login. The alias is resolved to the configured
admin email and then authenticated by the standard ``ModelBackend``.

The backend also normalises the typed email to lower case before the lookup,
and enforces the login-attempt lockout: while an account is locked, even the
correct PIN is refused (web, admin and API alike).
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

from .models import normalize_email

ADMIN_ALIAS = "admin"


def resolve_login_email(username):
    """Нэвтрэхэд бичсэн нэрийг и-мэйл болгож хөрвүүлнэ ("admin" → админ хаяг).

    Хариу нь үргэлж жижиг үсгээр гарна. Бүртгэл нь ч жижиг үсгээр хадгалагддаг
    (accounts.models.normalize_email) тул апп "Bataa@Gmail.com" гэж илгээсэн ч
    яг таарч нэвтэрнэ.
    """
    username = normalize_email(username)
    if username and "@" not in username and username == ADMIN_ALIAS:
        return normalize_email(getattr(settings, "ADMIN_ALIAS_EMAIL", ""))
    return username


class EmailOrAdminAliasBackend(ModelBackend):
    """ModelBackend that also accepts the literal ``admin`` as a login alias."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        User = get_user_model()  # noqa: N806
        if username is None:
            username = kwargs.get(User.USERNAME_FIELD)
        return super().authenticate(
            request, username=resolve_login_email(username), password=password, **kwargs
        )

    def user_can_authenticate(self, user):
        """Хаагдсан бүртгэл хаалт дуустал (эсвэл нууц үг сэргээх хүртэл) нэвтрэхгүй."""
        return super().user_can_authenticate(user) and not user.is_login_locked
