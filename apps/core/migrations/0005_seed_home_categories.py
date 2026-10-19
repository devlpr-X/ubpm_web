from django.db import migrations

# Өмнө нь views.py-д хатуу бичигдсэн байсан ангилалууд.
DEFAULTS = [
    ("Гар утас", "fa-solid fa-mobile-screen"),
    ("Нөүтбүүк", "fa-solid fa-laptop"),
    ("Таблет", "fa-solid fa-tablet-screen-button"),
    ("Камер", "fa-solid fa-camera"),
    ("Бусад", "fa-solid fa-box"),
]


def seed(apps, schema_editor):
    HomeCategory = apps.get_model("core", "HomeCategory")
    if HomeCategory.objects.exists():
        return
    HomeCategory.objects.bulk_create(
        HomeCategory(name=name, icon=icon, sort_order=i * 10)
        for i, (name, icon) in enumerate(DEFAULTS, start=1)
    )


class Migration(migrations.Migration):
    dependencies = [("core", "0004_homecategory")]

    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
