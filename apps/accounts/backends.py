"""Authentication backends for UBPM.

The project uses email as the login identifier. To make the Django admin
convenient, we let an operator type the literal username ``admin`` (instead of
the full email) at the admin login. The alias is resolved to the configured
admin email and then authenticated by the standard ``ModelBackend``.

The backend also enforces the login-attempt lockout: while an account is
locked, even the correct PIN is refused (web, admin and API alike).
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

ADMIN_ALIAS = "admin"


def resolve_login_email(username):
    """Нэвтрэхэд бичсэн нэрийг и-мэйл болгож хөрвүүлнэ ("admin" → админ хаяг)."""
    username = (username or "").strip()
    if username and "@" not in username and username.lower() == ADMIN_ALIAS:
        return getattr(settings, "ADMIN_ALIAS_EMAIL", "")
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
