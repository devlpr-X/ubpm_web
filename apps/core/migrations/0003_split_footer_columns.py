import re

from django.db import migrations

# Footer 2 баганатай болсон: утас, ажиллах цаг нь 2-р багана руу ("footer_contact"),
# © мөр base.html-ийн доод хэсэг рүү шилжсэн. Хуучин блокоос тэдгээрийг хасч
# товч танилцуулгаар орлуулна — эс бөгөөс давхар харагдана.
COPYRIGHT_DIV = re.compile(r"(<div><br></div>)?\s*<div>©[^<]*</div>")
CONTACT_DIV = re.compile(r"<div>(Утас|Ажиллах цаг):[^<]*</div>")

ABOUT = (
    "<div>Эвдэрсэн, хуучин гар утас, нөүтбүүк, таблет, камерыг ямар ч төлөвт нь "
    "өндөр үнээр, шуурхай, бэлнээр худалдан авна.</div>"
)


def split_footer(body):
    """Хуучин footer_main → (шинэ footer_main, footer_contact)."""
    contact = "".join(m.group(0) for m in CONTACT_DIV.finditer(body))
    main = CONTACT_DIV.sub("", COPYRIGHT_DIV.sub("", body)).strip()
    if contact:
        main += ABOUT
    return main, contact


def forwards(apps, schema_editor):
    SiteContent = apps.get_model("core", "SiteContent")
    block = SiteContent.objects.filter(key="footer_main").first()
    if block is None:
        return
    main, contact = split_footer(block.body)
    if main != block.body:
        block.body = main
        block.save(update_fields=["body"])
    if contact:
        SiteContent.objects.get_or_create(key="footer_contact", defaults={"body": contact})


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_sitecontent_link_label_sitecontent_link_url"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
