from django.contrib import admin

from .models import Pickup, Quotation, StatusHistory


@admin.register(Quotation)
class QuotationAdmin(admin.ModelAdmin):
    list_display = (
        "intake_request",
        "quoted_price_min",
        "quoted_price_max",
        "final_offer_price",
        "quoted_by",
        "sent_to_customer_at",
        "created_at",
    )
    list_filter = ("created_at", "quoted_by")
    search_fields = ("intake_request__request_code",)
    autocomplete_fields = ("intake_request", "quoted_by")


@admin.register(StatusHistory)
class StatusHistoryAdmin(admin.ModelAdmin):
    list_display = ("intake_request", "old_status", "new_status", "changed_by", "changed_at")
    list_filter = ("new_status", "changed_at")
    search_fields = ("intake_request__request_code",)
    readonly_fields = ("changed_at",)


@admin.register(Pickup)
class PickupAdmin(admin.ModelAdmin):
    list_display = (
        "intake_request",
        "pickup_date",
        "assigned_staff",
        "actual_buy_price",
        "payment_status",
        "payment_method",
    )
    list_filter = ("payment_status", "payment_method", "pickup_date")
    search_fields = ("intake_request__request_code", "pickup_address")
    autocomplete_fields = ("intake_request", "assigned_staff")
