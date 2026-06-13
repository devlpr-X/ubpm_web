from django.contrib import admin
from django.utils.html import format_html

from .models import DeviceCategory, DeviceImage, DeviceItem, IntakeRequest


@admin.register(DeviceCategory)
class DeviceCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "icon", "is_active", "sort_order")
    list_editable = ("sort_order", "is_active")
    prepopulated_fields = {"slug": ("name",)}


class DeviceImageInline(admin.TabularInline):
    model = DeviceImage
    extra = 0
    readonly_fields = ("preview",)
    fields = ("image", "preview", "sort_order")

    @admin.display(description="Preview")
    def preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height:60px;border-radius:4px;" />', obj.image.url
            )
        return "—"


class DeviceItemInline(admin.StackedInline):
    model = DeviceItem
    extra = 0
    show_change_link = True
    fields = (
        ("category", "brand", "model", "quantity"),
        ("storage", "color", "imei_or_serial"),
        ("power_on_status", "screen_status", "battery_status", "body_status"),
        ("water_damage", "condition_grade"),
        "accessories",
        "issue_description",
    )


@admin.register(IntakeRequest)
class IntakeRequestAdmin(admin.ModelAdmin):
    list_display = (
        "request_code",
        "contact_name",
        "contact_phone",
        "customer_type",
        "status",
        "preferred_branch",
        "assigned_to",
        "created_at",
    )
    list_filter = ("status", "customer_type", "source", "preferred_branch", "created_at")
    search_fields = (
        "request_code",
        "contact_name",
        "contact_phone",
        "contact_email",
        "company_name",
    )
    readonly_fields = ("request_code", "tracking_token", "created_at", "updated_at")
    inlines = [DeviceItemInline]
    fieldsets = (
        (None, {"fields": ("request_code", "tracking_token", "status", "source")}),
        (
            "Хэрэглэгч",
            {
                "fields": (
                    "submitted_by",
                    "customer_type",
                    "contact_name",
                    "company_name",
                    "contact_phone",
                    "contact_email",
                )
            },
        ),
        ("Хаяг", {"fields": ("city", "district", "address_line")}),
        (
            "Үйлчилгээ",
            {
                "fields": (
                    "preferred_branch",
                    "expected_price",
                    "pickup_required",
                    "assigned_to",
                )
            },
        ),
        ("Огноо", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(DeviceItem)
class DeviceItemAdmin(admin.ModelAdmin):
    list_display = ("intake_request", "category", "brand", "model", "quantity", "condition_grade")
    list_filter = ("category", "condition_grade", "power_on_status", "water_damage")
    search_fields = ("brand", "model", "imei_or_serial")
    inlines = [DeviceImageInline]


@admin.register(DeviceImage)
class DeviceImageAdmin(admin.ModelAdmin):
    list_display = ("device_item", "sort_order", "uploaded_at")
