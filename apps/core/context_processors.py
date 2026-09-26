"""Сайт даяар харагдах агуулгын template context (footer гэх мэт)."""

from django.db.utils import DatabaseError

from .models import SiteContent

FOOTER_KEY = "footer_main"
FOOTER_CONTACT_KEY = "footer_contact"

FOOTER_ABOUT = (
    "Эвдэрсэн, хуучин гар утас, нөүтбүүк, таблет, камерыг ямар ч төлөвт нь "
    "өндөр үнээр, шуурхай, бэлнээр худалдан авна."
)
FOOTER_CONTACT_DEFAULT = (
    "<div>Утас: 7774-6465 · 9915-6465 · 8025-6465</div>"
    "<div>Ажиллах цаг: 10:00–17:30 (амралтын өдөр ч)</div>"
)

# Footer дээрх сошиал линкүүд — тус бүр нэг SiteContent мөрийн link_url-д
# хадгалагдана. Дараалал нь footer дээр харагдах дараалал.
SOCIAL_KEYS = {
    "facebook": "social_facebook",
    "instagram": "social_instagram",
}


def footer_default():
    """Footer-ийн 1-р баганын анхны агуулга: нэр, товч танилцуулга.

    Trix нь class болон танихгүй тагуудыг хаядаг тул зөвхөн <div>, <strong>-оор
    хязгаарлав: админ эхний удаа хадгалахад ямар нэг зүйл чимээгүй алга болохгүй.
    Утас, ажиллах цаг нь 2-р баганад (FOOTER_CONTACT_KEY), © мөр base.html-ийн
    хамгийн доод хэсэгт байгаа тул энд орохгүй.
    """
    return f"<div><strong>UBPM ХХК</strong></div><div>{FOOTER_ABOUT}</div>"


def site_footer(request):
    """Footer-ийн блокийг бүх хуудсанд дамжуулна.

    base.html хуудас болгон дээр зурагддаг тул view тус бүрт нэмэхийн оронд
    context processor-оор өгөв. DB бэлэн биш үед (migrate хийгээгүй, алдааны
    хуудас) footer хоосон болохгүйн тулд хадгалаагүй блок руу ухарна.
    """
    try:
        block = SiteContent.get_block(FOOTER_KEY, default_body=footer_default())
        contact = SiteContent.get_block(FOOTER_CONTACT_KEY, default_body=FOOTER_CONTACT_DEFAULT)
    except DatabaseError:
        block = SiteContent(key=FOOTER_KEY, body=footer_default())
        contact = SiteContent(key=FOOTER_CONTACT_KEY, body=FOOTER_CONTACT_DEFAULT)
    return {
        "footer_content": block,
        "footer_contact": contact,
        "social_links": social_links(),
    }


def social_links():
    """{"facebook": {"url", "label"}, ...} — url хоосон бол тухайн лого харагдахгүй."""
    try:
        rows = {
            key: (url, label)
            for key, url, label in SiteContent.objects.filter(
                key__in=SOCIAL_KEYS.values()
            ).values_list("key", "link_url", "link_label")
        }
    except DatabaseError:
        rows = {}
    links = {}
    for name, key in SOCIAL_KEYS.items():
        url, label = rows.get(key, ("", ""))
        links[name] = {"url": url, "label": label}
    return links
