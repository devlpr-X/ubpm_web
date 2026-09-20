"""Хариуцагчгүй үлдсэн нээлттэй хүсэлтүүдийг үндсэн админ дээр ононо.

Одооноос хойш хүсэлт үүсэх мөчдөө ADMIN_ALIAS_EMAIL дээрх бүртгэл рүү очно
(`IntakeRequest.save`). Өмнө нь ирсэн, хараахан хаагдаагүй хүсэлтүүд нь
хариуцагчгүй үлдсэн тул хянах самбар дээр хагас нь «—» харагдах болно — эндээс
нэг удаа цэгцэлж, бүх нээлттэй хүсэлт эзэнтэй болгоно.

Хаагдсан (Зөвшөөрсөн / Худалдан авсан / Цуцалсан) хүсэлтэд хүрэхгүй — тэднийг
хэн ажилласан нь түүх, дараа нь оноосон мэт харагдуулах шаардлагагүй.
"""

from django.conf import settings
from django.db import migrations

OPEN_STATUSES = ["NEW", "PRICE_SENT", "APPROVED"]


def assign_open_requests(apps, schema_editor):
    email = (getattr(settings, "ADMIN_ALIAS_EMAIL", "") or "").strip().lower()
    if not email:
        return

    User = apps.get_model("accounts", "User")
    admin_id = (
        User.objects.filter(email__iexact=email, is_active=True)
        .values_list("pk", flat=True)
        .first()
    )
    if admin_id is None:
        return

    IntakeRequest = apps.get_model("intake", "IntakeRequest")
    IntakeRequest.objects.filter(
        assigned_to__isnull=True, status__in=OPEN_STATUSES
    ).update(assigned_to=admin_id)


def noop(apps, schema_editor):
    """Буцаах боломжгүй — аль нь анхнаасаа эзэнгүй байсныг ялгаж мэдэхгүй."""


class Migration(migrations.Migration):
    dependencies = [
        ("intake", "0007_category_icons_to_font_awesome"),
        ("accounts", "0007_lowercase_emails"),
    ]

    operations = [
        migrations.RunPython(assign_open_requests, noop),
    ]
