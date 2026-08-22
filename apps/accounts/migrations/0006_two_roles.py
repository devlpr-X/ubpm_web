"""Role-уудыг Админ / Хэрэглэгч гэсэн 2 болгож хураана.

Менежер, Оператор гэсэн role-ууд хянах самбарт Админтай яг ижил эрхтэй байсан
тул тусад нь байх шалтгаангүй болов. Одоо байгаа мөрүүдийг ADMIN болгож
буулгана — эрх нь өөрчлөгдөхгүй, зөвхөн нэр нь нэгдэнэ.
"""

from django.db import migrations, models

MERGED_INTO_ADMIN = ["MANAGER", "OPERATOR"]


def merge_staff_roles(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(role__in=MERGED_INTO_ADMIN).update(role="ADMIN")


def unmerge(apps, schema_editor):
    """Буцаах боломжгүй — аль нь менежер, аль нь оператор байсныг мэдэхгүй."""


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0005_user_pickup_lat_user_pickup_lng"),
    ]

    operations = [
        migrations.RunPython(merge_staff_roles, unmerge),
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[("ADMIN", "Админ"), ("CUSTOMER", "Хэрэглэгч")],
                default="CUSTOMER",
                max_length=20,
                verbose_name="Роль",
            ),
        ),
    ]
