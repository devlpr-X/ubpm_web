"""Email тохиргоог оношлох команд.

Ажиллаж буй орчны email тохиргоог хэвлээд туршилтын захиа илгээж, алдаа гарвал
жинхэнэ SMTP алдааг бүтнээр нь харуулна. Railway дээр:

    railway ssh "uv run python manage.py send_test_email you@example.com \
        --settings=ubpm.settings.prod"
"""

import smtplib

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Email тохиргоог шалгаж, туршилтын захиа илгээнэ."

    def add_arguments(self, parser):
        parser.add_argument("recipient", help="Захиа хүлээж авах email хаяг")
        parser.add_argument(
            "--no-send",
            action="store_true",
            help="Захиа илгээхгүй, зөвхөн SMTP холболт/нэвтрэлтийг шалгана.",
        )

    def handle(self, *args, **options):
        # Windows-ийн cp1252 консол дээр кирилл текст унахаас сэргийлнэ.
        for wrapper in (self.stdout, self.stderr):
            stream = getattr(wrapper, "_out", None)
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")

        recipient = options["recipient"]
        backend = settings.EMAIL_BACKEND
        password = getattr(settings, "EMAIL_HOST_PASSWORD", "")

        self.stdout.write(self.style.MIGRATE_HEADING("Одоогийн email тохиргоо"))
        for label, value in (
            ("EMAIL_BACKEND", backend),
            ("EMAIL_HOST", getattr(settings, "EMAIL_HOST", "")),
            ("EMAIL_PORT", getattr(settings, "EMAIL_PORT", "")),
            ("EMAIL_USE_TLS", getattr(settings, "EMAIL_USE_TLS", False)),
            ("EMAIL_USE_SSL", getattr(settings, "EMAIL_USE_SSL", False)),
            ("EMAIL_HOST_USER", getattr(settings, "EMAIL_HOST_USER", "")),
            # Нууц үгийг хэвлэхгүй — зөвхөн тавигдсан эсэх, уртыг нь харуулна.
            ("EMAIL_HOST_PASSWORD", f"<{len(password)} тэмдэгт>" if password else "<хоосон>"),
            ("EMAIL_TIMEOUT", getattr(settings, "EMAIL_TIMEOUT", None)),
            ("DEFAULT_FROM_EMAIL", settings.DEFAULT_FROM_EMAIL),
            ("EMAIL_ASYNC", getattr(settings, "EMAIL_ASYNC", True)),
            ("SITE_URL", getattr(settings, "SITE_URL", "")),
        ):
            self.stdout.write(f"  {label:22} = {value}")

        if "console" in backend or "locmem" in backend or "dummy" in backend:
            self.stdout.write("")
            raise CommandError(
                "EMAIL_BACKEND нь SMTP биш байна — захиа хэнд ч хүрэхгүй, зөвхөн log "
                "руу бичигдэнэ.\nЭнэ нь EMAIL_HOST_USER эсвэл EMAIL_HOST_PASSWORD "
                "тохируулагдаагүй үед prod дээр автоматаар унадаг нөөц горим юм.\n"
                "Railway → Variables дээр EMAIL_HOST_USER, EMAIL_HOST_PASSWORD-оо "
                "нэмээд дахин deploy хийнэ үү."
            )

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("SMTP холболт"))
        try:
            connection = get_connection()
            connection.open()
            self.stdout.write(self.style.SUCCESS("  ✔ Холбогдож, нэвтэрлээ."))
        # smtplib.SMTPException нь OSError-оос удамшдаг тул тодорхой алдаанууд
        # эхэлж бичигдэнэ — эс тэгвээс бүгд "холбогдож чадсангүй" болж харагдана.
        except smtplib.SMTPAuthenticationError as exc:
            raise CommandError(
                f"Gmail нэвтрэлт амжилтгүй: {exc!r}\n"
                "EMAIL_HOST_PASSWORD нь ЭНГИЙН нууц үг биш, Google Account → Security → "
                "2-Step Verification → App passwords дээрээс үүсгэсэн 16 тэмдэгт бүхий "
                "App Password байх ёстой."
            ) from exc
        except smtplib.SMTPException as exc:
            raise CommandError(f"SMTP серверийн алдаа: {exc!r}") from exc
        except (TimeoutError, OSError) as exc:
            raise CommandError(
                f"SMTP сервер рүү холбогдож чадсангүй: {exc!r}\n"
                f"Ихэвчлэн {settings.EMAIL_HOST}:{settings.EMAIL_PORT} порт нь hosting "
                "талаасаа хаалттай байдаг (Railway зэрэг платформууд spam-аас сэргийлж "
                "SMTP портыг хаадаг).\nШийдэл: EMAIL_PORT=465 + EMAIL_USE_SSL=True "
                "туршиж үзэх, эсвэл HTTP API-тай email үйлчилгээ (Resend, SendGrid) руу "
                "шилжих."
            ) from exc
        except Exception as exc:  # noqa: BLE001
            raise CommandError(f"SMTP холболт амжилтгүй: {exc!r}") from exc

        if options["no_send"]:
            connection.close()
            self.stdout.write(self.style.SUCCESS("Холболт хэвийн (захиа илгээгээгүй)."))
            return

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Туршилтын захиа"))
        msg = EmailMultiAlternatives(
            subject="UBPM — email тохиргооны тест",
            body=(
                "Энэ бол UBPM системийн email тохиргоог шалгасан туршилтын захиа.\n"
                "Хүлээн авсан бол мэдэгдлүүд (үнийн санал, нууц үг сэргээх код) "
                "хэвийн явж байна."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient],
            connection=connection,
        )
        try:
            sent = msg.send(fail_silently=False)
        except Exception as exc:  # noqa: BLE001
            raise CommandError(f"Захиа илгээхэд алдаа гарлаа: {exc!r}") from exc
        finally:
            connection.close()

        if not sent:
            raise CommandError("Захиа илгээгдсэнгүй (send() 0 буцаалаа).")
        self.stdout.write(
            self.style.SUCCESS(f"✔ {recipient} рүү илгээлээ. Spam хавтсаа ч шалгана уу.")
        )
