from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "UBPM удирдлага"
admin.site.site_title = "UBPM"
admin.site.index_title = "Системийн удирдлага"

urlpatterns = [
    path("admin/", admin.site.urls),
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
