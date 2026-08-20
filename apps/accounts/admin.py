from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import PasswordResetCode, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = (
        "email",
        "full_name",
        "role",
        "branch",
        "is_active",
        "lock_state",
        "date_joined",
    )
    list_filter = ("role", "is_active", "branch")
    search_fields = ("email", "full_name", "phone")
    ordering = ("email",)
    actions = ["unlock_accounts"]

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Хувийн мэдээлэл"), {"fields": ("full_name", "phone", "role", "branch")}),
        (
            _("Холбоо барих"),
            {
                "fields": (
                    "customer_type",
                    "company_name",
                    "city",
                    "district",
                    "address_line",
                )
            },
        ),
        (
            _("Эрх"),
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        (
            _("Нэвтрэх хамгаалалт"),
            {"fields": ("failed_login_attempts", "locked_until")},
        ),
        (_("Огноо"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "full_name", "role", "branch", "password1", "password2"),
            },
        ),
    )

    @admin.display(description=_("Хаалт"))
    def lock_state(self, obj):
        if obj.is_login_locked:
            return f"🔒 {obj.lockout_minutes_left} мин"
        if obj.failed_login_attempts:
            return f"{obj.failed_login_attempts} буруу оролдлого"
        return "—"

    @admin.action(description=_("Нэвтрэх хаалтыг тайлах"))
    def unlock_accounts(self, request, queryset):
        updated = queryset.update(failed_login_attempts=0, locked_until=None)
        self.message_user(request, f"{updated} бүртгэлийн хаалтыг тайллаа.")


@admin.register(PasswordResetCode)
class PasswordResetCodeAdmin(admin.ModelAdmin):
    list_display = ("user", "code", "created_at", "expires_at", "used_at")
    search_fields = ("user__email", "code")
    readonly_fields = ("created_at",)
