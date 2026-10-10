from django.contrib import admin

from .models import Conversation, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    fields = ("created_at", "from_staff", "sender", "body")
    readonly_fields = ("created_at",)


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("customer", "last_message_at")
    search_fields = ("customer__email", "customer__full_name", "customer__phone")
    raw_id_fields = ("customer",)
    inlines = [MessageInline]
