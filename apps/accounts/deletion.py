"""Хэрэглэгчийн бүртгэл, хувийн мэдээллийг устгах.

Нийтэлсэн бодлоготой (templates/public/account_delete.html) яг тааруулав:

* Нээлттэй хүсэлтүүд (Шинэ / Үнэ илгээсэн) — зураг, төхөөрөмж, түүхтэй нь
  бүхэлдээ устна.
* Шийдэгдсэн хүсэлтүүд (Зөвшөөрсөн / Худалдан авсан / Цуцалсан) — гүйлгээний
  бичлэг нь хууль, татвар, нягтлан бодох шаардлагаар үлдэнэ, харин хувийн
  мэдээлэл (нэр, утас, и-мэйл, хаяг, байршил) нь арилж, зургууд устна.
* Бүртгэл өөрөө устна — и-мэйл дахин ашиглах боломжтой болно.

Апп (`DELETE /api/v1/auth/me/`) болон вэб хоёулаа үүнийг дуудна, ингэснээр
хаанаас устгасан нь ялгаагүй ижил зүйл тохиолдоно.
"""

import logging

from django.db import transaction
from django.utils import timezone

from apps.intake.models import DeviceImage, IntakeRequest

logger = logging.getLogger(__name__)

# Шийдэгдсэн хүсэлтэд хувийн мэдээллийн оронд үлдэх тэмдэглэгээ.
ANONYMISED_NAME = "Устгасан хэрэглэгч"


def _delete_images(intake: IntakeRequest) -> int:
    """Хүсэлтийн бүх зургийг storage (R2/CDN)-аас устгана."""
    images = DeviceImage.objects.filter(device_item__intake_request=intake)
    count = 0
    # purge_device_images командтай ижил дараалал: файлыг илэрхий устгаж,
    # дараа нь мөрийг — ингэснээр CDN-д үлдэц хоцрохгүй.
    for image in images:
        if image.image:
            image.image.delete(save=False)
        image.delete()
        count += 1
    return count


def _anonymise(intake: IntakeRequest, now) -> None:
    intake.contact_name = ANONYMISED_NAME
    intake.company_name = ""
    intake.contact_phone = ""
    intake.contact_email = ""
    intake.district = ""
    intake.address_line = ""
    intake.pickup_lat = None
    intake.pickup_lng = None
    intake.images_purged_at = now
    intake.save(
        update_fields=[
            "contact_name",
            "company_name",
            "contact_phone",
            "contact_email",
            "district",
            "address_line",
            "pickup_lat",
            "pickup_lng",
            "images_purged_at",
            "updated_at",
        ]
    )


@transaction.atomic
def delete_account(user) -> dict:
    """`user`-ийн бүртгэл, хувийн мэдээллийг устгаад тоог нь мэдээлнэ."""
    now = timezone.now()
    deleted_requests = 0
    anonymised_requests = 0
    deleted_images = 0

    for intake in IntakeRequest.objects.filter(submitted_by=user):
        deleted_images += _delete_images(intake)
        if intake.status in IntakeRequest.OPEN_STATUSES:
            intake.delete()
            deleted_requests += 1
        else:
            _anonymise(intake, now)
            anonymised_requests += 1

    email = user.email
    # submitted_by нь SET_NULL тул үлдсэн (анонимчилсан) хүсэлтүүд хэвээр байна.
    user.delete()

    summary = {
        "deleted_requests": deleted_requests,
        "anonymised_requests": anonymised_requests,
        "deleted_images": deleted_images,
    }
    logger.info("Бүртгэл устгав: %s — %s", email, summary)
    return summary
