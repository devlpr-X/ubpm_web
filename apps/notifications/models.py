from django.db import models


class EmailLog(models.Model):
    recipient_email = models.EmailField("Хүлээн авагч")
    subject = models.CharField("Гарчиг", max_length=300)
    template_name = models.CharField("Template", max_length=100, blank=True)
    context_json = models.JSONField("Context", default=dict, blank=True)
    intake_request = models.ForeignKey(
        "intake.IntakeRequest",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="email_logs",
        verbose_name="Хүсэлт",
    )
    sent_at = models.DateTimeField(auto_now_add=True)
    success = models.BooleanField(default=True)
    error = models.TextField("Алдаа", blank=True)

    class Meta:
        ordering = ["-sent_at"]
        verbose_name = "Email log"
        verbose_name_plural = "Email logs"

    def __str__(self):
        return f"{self.recipient_email} — {self.subject}"


class PushDevice(models.Model):
    """Аппын push мэдэгдэл хүлээн авах төхөөрөмж (Expo push token)."""

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="push_devices",
        verbose_name="Хэрэглэгч",
    )
    token = models.CharField("Expo token", max_length=200, unique=True)
    platform = models.CharField("Платформ", max_length=10, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Push төхөөрөмж"
        verbose_name_plural = "Push төхөөрөмжүүд"

    def __str__(self):
        return f"{self.user} — {self.platform or '?'}"
