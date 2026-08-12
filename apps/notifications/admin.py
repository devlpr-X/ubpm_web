from django.contrib import admin

from .models import EmailLog


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = (
        "recipient_email",
        "subject",
        "template_name",
        "intake_request",
        "success",
        "short_error",
        "sent_at",
    )
    list_filter = ("success", "template_name", "sent_at")
    search_fields = ("recipient_email", "subject", "error")
    readonly_fields = ("sent_at",)

    @admin.display(description="Алдаа")
    def short_error(self, obj):
        """Явахгүй байгаа шалтгааныг жагсаалтаас шууд харах."""
        if obj.success:
            return "—"
        return (obj.error or "")[:120]
