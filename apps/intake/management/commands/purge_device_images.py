"""Шийдэгдсэн хүсэлтүүдийн зургийг CDN-ээс устгана.

Хүсэлт Зөвшөөрсөн / Худалдан авсан / Цуцалсан төлөвт орохад
`IntakeRequest.save()` нь `images_purge_at`-ыг (одоо + DEVICE_IMAGE_RETENTION_DAYS)
болгож тавьдаг. Энэ команд хугацаа нь болсон хүсэлтүүдийн зургийг устгана —
хүсэлтийн бусад мэдээлэл (үнэ, түүх, холбоо барих) хэвээр үлдэнэ.

Өдөрт нэг удаа cron-оор ажиллуулна:

    python manage.py purge_device_images
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.intake.models import DeviceImage, IntakeRequest


class Command(BaseCommand):
    help = "Хугацаа нь болсон шийдэгдсэн хүсэлтүүдийн зургийг устгана."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Юу устгахыг зөвхөн харуулна, өөрчлөлт хийхгүй.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        now = timezone.now()

        due = IntakeRequest.objects.filter(
            images_purge_at__lte=now, images_purged_at__isnull=True
        ).order_by("images_purge_at")

        total_images = 0
        total_requests = 0

        for intake in due:
            images = DeviceImage.objects.filter(device_item__intake_request=intake)
            count = images.count()

            if dry_run:
                self.stdout.write(f"[dry-run] {intake.request_code}: {count} зураг устгах байсан")
                total_images += count
                total_requests += 1
                continue

            # Файлыг storage-аас (R2/CDN) шууд устгана. django_cleanup мөн үүнийг
            # хийдэг ч зөвхөн transaction commit болсны дараа тул энд илэрхий
            # дуудаж, CDN-ээс арилсан эсэхэд эргэлзэхгүй байхаар хийв.
            for image in images:
                if image.image:
                    image.image.delete(save=False)
                image.delete()

            intake.images_purged_at = now
            intake.save(update_fields=["images_purged_at", "updated_at"])

            total_images += count
            total_requests += 1
            self.stdout.write(f"{intake.request_code}: {count} зураг устгалаа")

        prefix = "[dry-run] " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}{total_requests} хүсэлтийн нийт {total_images} зураг цэвэрлэгдлээ."
            )
        )
