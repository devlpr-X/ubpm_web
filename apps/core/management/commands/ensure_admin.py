"""Create the default admin superuser if it is missing (idempotent).

Login (Django admin at /admin/):  admin  /  1234 (анх үүсэх үед).
The literal username ``admin`` is resolved to ADMIN_ALIAS_EMAIL by
apps.accounts.backends.EmailOrAdminAliasBackend.

Container эхлэх бүрт (Dockerfile) ажилладаг тул ЗААВАЛ мөрддөг дүрэм:
байгаа админы нууц үгэнд хүрэхгүй. Өмнө нь энэ команд ажиллах болгондоо
`set_password("1234")` хийдэг байсан — үүнээс болж админ нууц үгээ солих
бүрд дараагийн deploy түүнийг нь буцааж, "Please enter a correct Email and
password" гэж заадаг байв. Нууц үгийг зориуд солих бол `--password`-ыг
шууд дамжуулна (`manage.py ensure_admin --password=...`).
"""

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.accounts.models import User

# Өмнө нь ашиглаж байсан админ хаягууд — ADMIN_ALIAS_EMAIL өөрчлөгдөхөд эдгээр
# дээрх бүртгэлийг шинэ хаяг руу нь шилжүүлнэ.
LEGACY_ADMIN_EMAILS = ["admin@ubpm.mn"]

# Админ анх удаа үүсэх үеийн нууц үг. Дараа нь солибол тэр нь хэвээр үлдэнэ.
DEFAULT_PASSWORD = "1234"


class Command(BaseCommand):
    help = "Ensure the default admin superuser exists (does not touch an existing password)"

    def add_arguments(self, parser):
        # default=None — "өгөөгүй" гэдгийг ялгаж мэдэхийн тулд. Өгөөгүй үед
        # зөвхөн шинээр үүсэж буй админд DEFAULT_PASSWORD тавина.
        parser.add_argument(
            "--password",
            default=None,
            help="Нууц үгийг хүчээр солих (өгөөгүй бол байгаа нууц үг хэвээр үлдэнэ)",
        )
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
        # Эрхийг нь deploy бүрт сэргээнэ — админ санамсаргүй эрхээ алдвал
        # дараагийн гаралтаар өөрөө засагдана. Нууц үг үүнд ордоггүй.
        user.role = User.Role.ADMIN
        user.is_staff = True
        user.is_superuser = True
        if created or password:
            user.set_password(password or DEFAULT_PASSWORD)
        user.save()

        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Үүсгэв: {email} / {password or DEFAULT_PASSWORD}  "
                    f"(нэвтрэх: admin / {password or DEFAULT_PASSWORD})"
                )
            )
        elif password:
            self.stdout.write(self.style.SUCCESS(f"Нууц үг солив: {email}"))
        else:
            self.stdout.write(f"Байна: {email} — нууц үгэнд хүрсэнгүй.")
