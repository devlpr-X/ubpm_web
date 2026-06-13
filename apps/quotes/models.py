from django.conf import settings
from django.db import models


class Quotation(models.Model):
    intake_request = models.ForeignKey(
        "intake.IntakeRequest",
        on_delete=models.CASCADE,
        related_name="quotes",
        verbose_name="Хүсэлт",
    )
    quoted_price_min = models.DecimalField("Хамгийн доод үнэ", max_digits=12, decimal_places=2)
    quoted_price_max = models.DecimalField("Хамгийн дээд үнэ", max_digits=12, decimal_places=2)
    final_offer_price = models.DecimalField(
        "Эцсийн санал", max_digits=12, decimal_places=2, null=True, blank=True
    )
    note = models.TextField("Тэмдэглэл", blank=True)
    valid_until = models.DateField("Хүчинтэй хугацаа", null=True, blank=True)
    quoted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="quotations",
        verbose_name="Үнэлгээ хийсэн",
    )
    sent_to_customer_at = models.DateTimeField("Хэрэглэгчид илгээсэн", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Үнэ санал"
        verbose_name_plural = "Үнэ саналууд"

    def __str__(self):
        return f"{self.intake_request.request_code} — {self.quoted_price_min}-{self.quoted_price_max}"


class StatusHistory(models.Model):
    intake_request = models.ForeignKey(
        "intake.IntakeRequest",
        on_delete=models.CASCADE,
        related_name="history",
        verbose_name="Хүсэлт",
    )
    old_status = models.CharField("Хуучин статус", max_length=20, blank=True)
    new_status = models.CharField("Шинэ статус", max_length=20)
    comment = models.TextField("Тайлбар", blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="status_changes",
        verbose_name="Өөрчилсөн",
    )
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-changed_at"]
        verbose_name = "Статусын түүх"
        verbose_name_plural = "Статусын түүх"

    def __str__(self):
        return f"{self.intake_request.request_code}: {self.old_status} → {self.new_status}"


class Pickup(models.Model):
    class PaymentStatus(models.TextChoices):
        PENDING = "PENDING", "Хүлээгдэж буй"
        PAID = "PAID", "Төлөгдсөн"

    class PaymentMethod(models.TextChoices):
        CASH = "CASH", "Бэлэн мөнгө"
        BANK = "BANK", "Банк шилжүүлэг"

    intake_request = models.OneToOneField(
        "intake.IntakeRequest",
        on_delete=models.CASCADE,
        related_name="pickup",
        verbose_name="Хүсэлт",
    )
    pickup_date = models.DateTimeField("Pickup-ийн огноо")
    pickup_address = models.CharField("Pickup хаяг", max_length=500)
    assigned_staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="pickups",
        verbose_name="Хариуцсан ажилтан",
    )
    actual_buy_price = models.DecimalField(
        "Бодит худалдан авсан үнэ", max_digits=12, decimal_places=2, null=True, blank=True
    )
    payment_status = models.CharField(
        "Төлбөрийн төлөв",
        max_length=10,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
    )
    payment_method = models.CharField(
        "Төлбөрийн арга",
        max_length=10,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH,
    )
    notes = models.TextField("Тэмдэглэл", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-pickup_date"]
        verbose_name = "Pickup"
        verbose_name_plural = "Pickup-үүд"

    def __str__(self):
        return f"Pickup — {self.intake_request.request_code}"
