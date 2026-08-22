"""Сайт даяар харагдах агуулгын template context (footer гэх мэт)."""

from django.db.utils import DatabaseError
from django.utils import timezone

from .models import SiteContent

FOOTER_KEY = "footer_main"


def footer_default():
    """Footer-ийн анхны агуулга — өмнө нь base.html дотор бичээстэй байсан хэсэг.

    Trix нь class болон танихгүй тагуудыг хаядаг тул зөвхөн <div>, <strong>-оор
    хязгаарлав: админ эхний удаа хадгалахад ямар нэг зүйл чимээгүй алга болохгүй.
    Он нь эхний удаа үүсгэх үед бичигдэнэ — цаашид footer-ээсээ шууд засна.
    """
    return (
        "<div><strong>UBPM ХХК</strong></div>"
        "<div>Утас: 7774-6465 · 9915-6465 · 8025-6465</div>"
        "<div>Ажиллах цаг: 10:00–17:30 (амралтын өдөр ч)</div>"
        "<div><br></div>"
        f"<div>© {timezone.localdate().year} UBPM. Бүх эрх хуулиар хамгаалагдсан.</div>"
    )


def site_footer(request):
    """Footer-ийн блокийг бүх хуудсанд дамжуулна.

    base.html хуудас болгон дээр зурагддаг тул view тус бүрт нэмэхийн оронд
    context processor-оор өгөв. DB бэлэн биш үед (migrate хийгээгүй, алдааны
    хуудас) footer хоосон болохгүйн тулд хадгалаагүй блок руу ухарна.
    """
    try:
        block = SiteContent.get_block(FOOTER_KEY, default_body=footer_default())
    except DatabaseError:
        block = SiteContent(key=FOOTER_KEY, body=footer_default())
    return {"footer_content": block}
