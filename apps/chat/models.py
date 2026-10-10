"""Хэрэглэгч ↔ админ энгийн текст чат.

Хэрэглэгч бүр ганц яриатай (Conversation); ажилтнууд бүгд түүнийг хамтдаа
харж хариулна. Мессеж нь зөвхөн текст.
"""

from django.conf import settings
from django.db import models

MAX_MESSAGE_LENGTH = 1000


class Conversation(models.Model):
    customer = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conversation",
        verbose_name="Хэрэглэгч",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    # Сүүлийн мессежийн цаг — ажилтны жагсаалтыг эрэмбэлнэ.
    last_message_at = models.DateTimeField(null=True, blank=True, db_index=True)
    # Уншаагүй эсэхийг нэмэлт query-гүйгээр мэдэхийн тулд: тал бүрийн сүүлийн
    # мессежийн id болон тал бүр хамгийн сүүлд уншсан id.
    last_customer_message_id = models.BigIntegerField(default=0)
    last_staff_message_id = models.BigIntegerField(default=0)
    customer_last_read_id = models.BigIntegerField(default=0)
    staff_last_read_id = models.BigIntegerField(default=0)

    class Meta:
        ordering = ("-last_message_at", "-id")
        verbose_name = "Чат"
        verbose_name_plural = "Чатууд"

    def __str__(self):
        return f"Чат: {self.customer}"

    @property
    def unread_for_staff(self):
        return self.last_customer_message_id > self.staff_last_read_id

    @property
    def unread_for_customer(self):
        return self.last_staff_message_id > self.customer_last_read_id


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    # Ажилтан бичсэн эсэх — илгээгч устсан ч аль талынх нь мэдэгдэнэ.
    from_staff = models.BooleanField(default=False)
    body = models.TextField(max_length=MAX_MESSAGE_LENGTH)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("id",)
        verbose_name = "Мессеж"
        verbose_name_plural = "Мессежүүд"

    def __str__(self):
        return self.body[:50]
