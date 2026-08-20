"""Create or update the default admin superuser (idempotent).

Login (Django admin at /admin/):  admin  /  1234
The literal username ``admin`` is resolved to ADMIN_ALIAS_EMAIL by
apps.accounts.backends.EmailOrAdminAliasBackend.
"""

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.accounts.models import User

# Өмнө нь ашиглаж байсан админ хаягууд — ADMIN_ALIAS_EMAIL өөрчлөгдөхөд эдгээр
# дээрх бүртгэлийг шинэ хаяг руу нь шилжүүлнэ.
LEGACY_ADMIN_EMAILS = ["admin@ubpm.mn"]


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

        # Админ хаяг өөрчлөгдсөн бол хуучин бүртгэлийг ШИНЭ хаяг руу нь
        # шилжүүлнэ — эс бөгөөс хоёр супер хэрэглэгч үлдэж, хуучин дээрх
        # түүх/хүсэлтүүд салангид болно.
        if not User.objects.filter(email=email).exists():
            legacy = User.objects.filter(email__in=LEGACY_ADMIN_EMAILS).first()
            if legacy:
                legacy.email = email
                legacy.save(update_fields=["email"])
                self.stdout.write(f"Хуучин админ хаягийг шилжүүлэв → {email}")

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
