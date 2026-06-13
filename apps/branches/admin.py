from django.contrib import admin

from .models import Branch, BranchMedia, PartnerLocation


class BranchMediaInline(admin.TabularInline):
    model = BranchMedia
    extra = 0
    fields = ("media_type", "file", "caption", "sort_order")


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "city", "district", "is_active")
    list_filter = ("is_active", "city", "district")
    search_fields = ("name", "code", "address_line")
    prepopulated_fields = {"code": ("name",)}
    inlines = [BranchMediaInline]
    fieldsets = (
        (None, {"fields": ("name", "code", "is_active")}),
        ("Хаяг", {"fields": ("address_line", "city", "district", "latitude", "longitude")}),
        ("Холбоо барих", {"fields": ("phones", "working_hours")}),
        ("Танилцуулга", {"fields": ("cover_image", "description")}),
    )


@admin.register(PartnerLocation)
class PartnerLocationAdmin(admin.ModelAdmin):
    list_display = ("name", "partner_company", "address", "phone", "is_active")
    list_filter = ("is_active", "partner_company")
    search_fields = ("name", "partner_company", "address")


@admin.register(BranchMedia)
class BranchMediaAdmin(admin.ModelAdmin):
    list_display = ("branch", "media_type", "caption", "sort_order")
    list_filter = ("media_type", "branch")
