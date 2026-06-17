from django.contrib import messages
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView

from apps.accounts.views import staff_required

from .models import SiteContent

# Default content seeded into the editable "about_main" block on first view.
ABOUT_DEFAULT_TITLE = "UBPM ХХК — Танилцуулга"
ABOUT_DEFAULT_BODY = """
<p>Бид 2018 оноос хойш Монгол улсад эвдэрсэн, ашиглахаа больсон төхөөрөмжүүдийг
<strong>өндөр үнээр, шуурхай, бэлнээр</strong> худалдан авч байна. Манайхаар
үйлчлүүлэхдээ та зүгээр нэг зураг авч илгээхэд л хангалттай — үлдсэн ажлыг бид
хариуцана.</p>

<h2 class="text-lg font-semibold mt-6">Худалдан авдаг бүтээгдэхүүн</h2>
<ul class="mt-2 list-disc list-inside text-gray-700 space-y-1">
  <li>Гар утас (iPhone, Samsung, Huawei г.м.)</li>
  <li>Нөүтбүүк / MacBook</li>
  <li>Таблет / iPad</li>
  <li>Цахилгаан камер</li>
  <li>Утасны эд анги — плат, дэлгэц, батарей</li>
  <li>Бусад электроник төхөөрөмжүүд</li>
</ul>
""".strip()


HOME_HERO_DEFAULT = (
    "<p>Гар утас, нөүтбүүк, таблет, камер — ямар ч төлөвт байсан үнэлж авна. "
    "<strong>Өндөр үнээр, шуурхай, бэлнээр.</strong></p>"
)
HOME_HOW_DEFAULT = (
    "<ol>"
    "<li>Та утаснаасаа хүсэлт илгээнэ (4 алхам, ~2 минут)</li>"
    "<li>Манай оператор үнэлгээ хийж үнэ санал илгээнэ</li>"
    "<li>Та зөвшөөрвөл салбар дээр эсвэл хүргэлтээр бэлэн мөнгөөр төлбөр хийнэ</li>"
    "</ol>"
)


class HomeView(TemplateView):
    template_name = "public/home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["categories"] = [
            {"name": "Гар утас", "emoji": "📱"},
            {"name": "Нөүтбүүк", "emoji": "💻"},
            {"name": "Таблет", "emoji": "📲"},
            {"name": "Камер", "emoji": "📷"},
            {"name": "Утасны плат", "emoji": "🔧"},
            {"name": "Бусад", "emoji": "📦"},
        ]
        ctx["hero"] = SiteContent.get_block("home_hero", default_body=HOME_HERO_DEFAULT)
        ctx["how"] = SiteContent.get_block(
            "home_how", default_title="Хэрхэн ажилладаг вэ?", default_body=HOME_HOW_DEFAULT
        )
        return ctx


class AboutView(TemplateView):
    template_name = "public/about.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from django.conf import settings

        ctx["content"] = SiteContent.get_block(
            "about_main",
            default_title=ABOUT_DEFAULT_TITLE,
            default_body=ABOUT_DEFAULT_BODY,
        )
        ctx["MAX_VIDEO_SIZE_MB"] = settings.MAX_VIDEO_SIZE_MB
        return ctx


class ContactView(TemplateView):
    template_name = "public/contact.html"


class FaqView(TemplateView):
    template_name = "public/faq.html"


class PrivacyView(TemplateView):
    template_name = "public/privacy.html"


class AccountDeleteView(TemplateView):
    template_name = "public/account_delete.html"


@staff_required
@require_POST
def content_edit(request, key):
    """Save an admin-edited SiteContent block, then return to the page."""
    block = SiteContent.objects.filter(key=key).first()
    if block is None:
        block = SiteContent(key=key)

    block.title = request.POST.get("title", block.title)
    block.body = request.POST.get("body", block.body)
    block.video_url = request.POST.get("video_url", "").strip()

    if request.POST.get("remove_video") == "1" and block.video:
        block.video.delete(save=False)
        block.video = None

    upload = request.FILES.get("video")
    if upload and _video_ok(request, upload):
        block.video = upload

    block.updated_by = request.user
    block.save()
    messages.success(request, "Агуулга шинэчлэгдлээ.")
    return redirect(_safe_next(request) or "core:about")


def _safe_next(request):
    nxt = request.POST.get("next", "")
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        return nxt
    return ""


def _video_ok(request, f):
    from django.conf import settings

    limit = settings.MAX_VIDEO_SIZE_MB * 1024 * 1024
    if f.size > limit:
        messages.error(
            request,
            f"Бичлэг хэт том байна ({settings.MAX_VIDEO_SIZE_MB}MB-аас бага байх ёстой). Хадгалсангүй.",
        )
        return False
    return True
