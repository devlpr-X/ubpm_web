from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path
from django.views.generic import TemplateView

from apps.core.sitemaps import sitemaps

admin.site.site_header = "UBPM удирдлага"
admin.site.site_title = "UBPM"
admin.site.index_title = "Системийн удирдлага"


class RobotsView(TemplateView):
    """robots.txt — the Sitemap line follows whichever host served the request."""

    template_name = "robots.txt"
    content_type = "text/plain"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["scheme"] = self.request.scheme
        ctx["host"] = self.request.get_host()
        return ctx


urlpatterns = [
    path("admin/", admin.site.urls),
    path("robots.txt", RobotsView.as_view(), name="robots"),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="django.contrib.sitemaps.views.sitemap"),
    path("api/v1/", include("apps.api.urls", namespace="api")),
    path("accounts/", include("apps.accounts.urls", namespace="accounts")),
    path("request/", include("apps.intake.urls", namespace="intake")),
    path("dashboard/", include("apps.reports.urls")),
    path("branches/", include("apps.branches.urls", namespace="branches")),
    path("", include("apps.core.urls", namespace="core")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
