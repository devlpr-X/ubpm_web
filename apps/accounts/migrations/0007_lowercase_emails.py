"""Байгаа бүртгэлүүдийн и-мэйлийг жижиг үсэг болгоно.

Одооноос хойш бүртгэх, нэвтрэх бүх зам и-мэйлийг жижиг үсгээр нэг хэлбэрт
оруулдаг болсон (accounts.models.normalize_email). Хуучин мөрүүд том үсэгтэй
үлдвэл тэр хүмүүс нэвтэрч чадахгүй тул энд нэг удаа цэгцэлнэ.

Хоёр мөр зөвхөн үсгийн хэмжээгээрээ ялгаатай байх (ж: "Bataa@x.mn" ба
"bataa@x.mn") ховор боловч боломжтой. Тийм мөрийг ХЭВЭЭР үлдээнэ — нэгтгэх нь
аль хүсэлт нь хэний байсныг шийдэхийг шаардах тул автоматаар хийхгүй.
"""

from django.db import migrations


def lowercase_emails(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    taken = set(User.objects.values_list("email", flat=True))

    for pk, email in User.objects.values_list("pk", "email"):
        lowered = (email or "").strip().lower()
        if lowered == email or not lowered:
            continue
        if lowered in taken:
            continue
        User.objects.filter(pk=pk).update(email=lowered)
        taken.discard(email)
        taken.add(lowered)


def noop(apps, schema_editor):
    """Буцаах боломжгүй — анх ямар үсгээр бичсэнийг мэдэхгүй."""


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0006_two_roles"),
    ]

    operations = [
        migrations.RunPython(lowercase_emails, noop),
    ]
