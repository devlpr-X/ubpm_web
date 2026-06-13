"""Create or update the default admin superuser (idempotent).

Login (Django admin at /admin/):  admin  /  1234
The literal username ``admin`` is resolved to ADMIN_ALIAS_EMAIL by
apps.accounts.backends.EmailOrAdminAliasBackend.
"""

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.accounts.models import User


class Command(BaseCommand):
    help = "Ensure the default admin superuser (admin / 1234) exists"

    def add_arguments(self, parser):
        parser.add_argument("--password", default="1234")
        parser.add_argument(
            "--email", default=getattr(settings, "ADMIN_ALIAS_EMAIL", "admin@ubpm.mn")
        )

    def handle(self, *args, **opts):
        email = opts["email"]
        password = opts["password"]
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "full_name": "Админ",
                "role": User.Role.ADMIN,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        user.role = User.Role.ADMIN
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save()

        verb = "Үүсгэв" if created else "Шинэчлэв"
        self.stdout.write(
            self.style.SUCCESS(f"{verb}: {email} / {password}  (нэвтрэх: admin / {password})")
        )
