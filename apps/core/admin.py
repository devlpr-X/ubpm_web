from django.contrib import admin

from .models import SiteContent


@admin.register(SiteContent)
class SiteContentAdmin(admin.ModelAdmin):
    list_display = ("key", "title", "updated_at", "updated_by")
    readonly_fields = ("updated_at", "updated_by")
    search_fields = ("key", "title", "body")
