"""Authentication backends for UBPM.

The project uses email as the login identifier. To make the Django admin
convenient, we let an operator type the literal username ``admin`` (instead of
the full email) at the admin login. The alias is resolved to the configured
admin email and then authenticated by the standard ``ModelBackend``.
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

ADMIN_ALIAS = "admin"


class EmailOrAdminAliasBackend(ModelBackend):
    """ModelBackend that also accepts the literal ``admin`` as a login alias."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        User = get_user_model()  # noqa: N806
        if username is None:
            username = kwargs.get(User.USERNAME_FIELD)
        if username and "@" not in username and username.strip().lower() == ADMIN_ALIAS:
            username = getattr(settings, "ADMIN_ALIAS_EMAIL", "admin@ubpm.mn")
        return super().authenticate(
            request, username=username, password=password, **kwargs
        )
