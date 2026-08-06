from django.db import migrations


def deactivate_phone_board(apps, schema_editor):
    DeviceCategory = apps.get_model("intake", "DeviceCategory")
    DeviceCategory.objects.filter(slug="phone-board").update(is_active=False)
    DeviceCategory.objects.filter(name="Утасны плат").update(is_active=False)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("intake", "0004_intakerequest_pickup_lat_intakerequest_pickup_lng_and_more"),
    ]

    operations = [
        migrations.RunPython(deactivate_phone_board, noop),
    ]
