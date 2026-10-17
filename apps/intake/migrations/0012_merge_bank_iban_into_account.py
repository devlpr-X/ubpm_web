from django.db import migrations
from django.db.models import Q


def merge_iban_into_account(apps, schema_editor):
    """Дансны дугаар хоосон бол өмнө оруулсан IBAN-ыг түүнд шилжүүлнэ."""
    Model = apps.get_model("intake", "IntakeRequest")
    for obj in Model.objects.filter(Q(bank_account="") & ~Q(bank_iban="")):
        obj.bank_account = obj.bank_iban
        obj.save(update_fields=["bank_account"])


class Migration(migrations.Migration):
    dependencies = [
        ("intake", "0011_intakerequest_bank_iban"),
    ]

    operations = [
        migrations.RunPython(merge_iban_into_account, migrations.RunPython.noop),
        migrations.RemoveField(model_name="intakerequest", name="bank_iban"),
    ]
