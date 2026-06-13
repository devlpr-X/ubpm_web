from django.contrib import admin

from .models import EmailLog


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ("recipient_email", "subject", "template_name", "intake_request", "success", "sent_at")
    list_filter = ("success", "template_name", "sent_at")
    search_fields = ("recipient_email", "subject")
    readonly_fields = ("sent_at",)
