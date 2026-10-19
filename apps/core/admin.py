from django.contrib import admin

from .models import HomeCategory, SiteContent, SiteContentImage


class SiteContentImageInline(admin.TabularInline):
    model = SiteContentImage
    extra = 1
    fields = ("image", "sort_order")


@admin.register(SiteContent)
class SiteContentAdmin(admin.ModelAdmin):
    inlines = [SiteContentImageInline]
    list_display = ("key", "title", "updated_at", "updated_by")
    readonly_fields = ("updated_at", "updated_by")
    search_fields = ("key", "title", "body")


@admin.register(HomeCategory)
class HomeCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "icon", "sort_order", "is_active")
    list_editable = ("icon", "sort_order", "is_active")
    search_fields = ("name",)
