"""Ангиллын emoji дүрсийг Font Awesome Free-ийн класс болгож хөрвүүлнэ.

Загварын дүрсүүд emoji-гаас icon font руу шилжсэн (templates/base.html дээр
Font Awesome ачаалдаг) тул DB-д хадгалагдсан утгууд ч мөн класс байх ёстой.
"""

from django.db import migrations, models

# emoji → Font Awesome Free класс. Мэдэгдэхгүй emoji нь fa-solid fa-box болно.
EMOJI_TO_ICON = {
    "\U0001F4F1": "fa-solid fa-mobile-screen",  # 📱 гар утас
    "\U0001F4F2": "fa-solid fa-tablet-screen-button",  # 📲 таблет
    "\U0001F4BB": "fa-solid fa-laptop",  # 💻 нөүтбүүк
    "\U0001F5A5": "fa-solid fa-desktop",  # 🖥 компьютер
    "\U0001F4F7": "fa-solid fa-camera",  # 📷 камер
    "\U0001F4F9": "fa-solid fa-video",  # 📹 видео камер
    "\U0001F4E6": "fa-solid fa-box",  # 📦 бусад
    "\U0001F3A7": "fa-solid fa-headphones",  # 🎧 чихэвч
    "⌚": "fa-solid fa-clock",  # ⌚ цаг
    "\U0001F5A8": "fa-solid fa-print",  # 🖨 принтер
    "\U0001F50B": "fa-solid fa-battery-half",  # 🔋 батарей
    "\U0001F527": "fa-solid fa-wrench",  # 🔧 засвар
}
FALLBACK_ICON = "fa-solid fa-box"


def _looks_like_icon_class(value):
    return "fa-" in value


def to_font_awesome(apps, schema_editor):
    DeviceCategory = apps.get_model("intake", "DeviceCategory")
    for category in DeviceCategory.objects.exclude(icon=""):
        icon = category.icon.strip()
        if _looks_like_icon_class(icon):
            continue  # аль хэдийн класс болсон — дахин хөрвүүлэхгүй
        category.icon = EMOJI_TO_ICON.get(icon, FALLBACK_ICON)
        category.save(update_fields=["icon"])


def noop_reverse(apps, schema_editor):
    """Буцаах шаардлагагүй — хуучин emoji-г сэргээх мэдээлэл хадгалаагүй."""


class Migration(migrations.Migration):
    dependencies = [
        ("intake", "0006_intakerequest_images_purge_at_and_more"),
    ]

    operations = [
        migrations.RunPython(to_font_awesome, noop_reverse),
        migrations.AlterField(
            model_name="devicecategory",
            name="icon",
            field=models.CharField(
                blank=True,
                help_text='Font Awesome класс, ж: "fa-solid fa-mobile-screen"',
                max_length=50,
                verbose_name="Дүрс (icon класс)",
            ),
        ),
    ]
