"""Canonical host redirect — ubpm.mn бол сайтын цорын ганц индекслэгдэх хуулбар."""

from django.conf import settings
from django.core.exceptions import DisallowedHost, MiddlewareNotUsed
from django.http import HttpResponsePermanentRedirect


class CanonicalHostRedirectMiddleware:
    """CANONICAL_HOST биш host руу ирсэн хүсэлтийг 301-ээр шилжүүлнэ.

    Railway сайтыг custom домайноос гадна <project>.up.railway.app дээр бас
    үйлчилдэг. Хоёул өөрийгөө заасан canonical таг буцаадаг байсан тул хайлтын
    систем хоёр ижил сайт харж, эрэмбийг нь хооронд нь хуваадаг байв.

    CANONICAL_HOST env var-ыг хоосон болговол энэ шилжүүлэг унтарч, Railway
    домайн дахин бүрэн ажиллагаатай нөөц (fallback) болно — ubpm.mn ажиллахаа
    больсон үед л ингэнэ.

    CANONICAL_EXEMPT_PREFIXES дэх замууд шилжихгүй. Мобайл апп нь ubpm.mn
    ажиллахгүй үед Railway домайн руу шилждэг тул /api/ заавал чөлөөлөгдөнө:
    301 дээр POST нь GET болж хувирдаг учир хүсэлтийн бие алдагдана.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.canonical_host = getattr(settings, "CANONICAL_HOST", "")
        self.exempt_prefixes = tuple(getattr(settings, "CANONICAL_EXEMPT_PREFIXES", ()))
        if not self.canonical_host:
            # Dev болон fallback горимд middleware-ийг огт ачаалахгүй.
            raise MiddlewareNotUsed

    def __call__(self, request):
        if request.path.startswith(self.exempt_prefixes):
            return self.get_response(request)

        try:
            host = request.get_host()
        except DisallowedHost:
            # ALLOWED_HOSTS-д байхгүй host. Үүнийг 400-аар унагахын оронд үндсэн
            # домайн руу шилжүүлнэ — Railway домайн болон энэ сервис рүү заасан
            # хамаагүй домайн бүр 400 биш 301 авна.
            host = None

        if host != self.canonical_host:
            # Схемийг үргэлж https болгож, буруу host + буруу схемийг нэг л
            # үсрэлтээр залруулна (SecurityMiddleware-ийн SSL redirect-ээс өмнө).
            return HttpResponsePermanentRedirect(
                f"https://{self.canonical_host}{request.get_full_path()}"
            )
        return self.get_response(request)
