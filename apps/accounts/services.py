"""Login-attempt limiting and password-reset-by-email-code logic.

Shared by the web views and the API so the mobile app behaves the same way.
"""

import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import PasswordResetCode, User

logger = logging.getLogger(__name__)


def _ttl():
    minutes = getattr(settings, "PASSWORD_RESET_CODE_TTL_MINUTES", 15)
    return timedelta(minutes=minutes)


def max_login_attempts() -> int:
    return getattr(settings, "ACCOUNT_LOCKOUT_MAX_ATTEMPTS", 5)


def lockout_minutes() -> int:
    return getattr(settings, "ACCOUNT_LOCKOUT_MINUTES", 30)


def generate_code() -> str:
    """A random 4-digit code, zero-padded (e.g. '0421')."""
    return f"{secrets.randbelow(10000):04d}"


def _active_user(email: str):
    return User.objects.filter(email__iexact=(email or "").strip(), is_active=True).first()


def _issue_code(user) -> str:
    """Store a fresh one-time code for the account and return it."""
    code = generate_code()
    PasswordResetCode.objects.create(
        user=user, code=code, expires_at=timezone.now() + _ttl()
    )
    return code


def send_reset_code(email: str) -> bool:
    """Create a reset code for the account and email it.

    Returns True if a code was sent. Always behaves the same to the caller to
    avoid leaking whether an email is registered.
    """
    user = _active_user(email)
    if not user:
        return False

    code = _issue_code(user)

    # Local import avoids a circular import at module load time.
    from apps.notifications.services import send_password_reset_code_email

    send_password_reset_code_email(user, code)
    return True


# ---------------------------------------------------------------------------
# Нэвтрэх оролдлогын хязгаар
# ---------------------------------------------------------------------------


def register_failed_login(email: str) -> None:
    """Буруу нууц үгийн оролдлогыг тоолж, хязгаараас хэтэрвэл бүртгэлийг хаана.

    Хаагдах мөчид хэрэглэгчийн и-мэйл рүү сэргээх кодыг шууд илгээнэ — тэр
    хүн зүгээр л шуудангаа нээж, кодоо оруулаад шинэ PIN тавьж орох боломжтой.
    """
    user = _active_user(email)
    if not user or user.is_login_locked:
        # Бүртгэлгүй и-мэйл дээр тоолох зүйлгүй; аль хэдийн хаагдсан бол
        # оролдлого бүрт шинэ код илгээхгүй (шуудан дүүргэхээс сэргийлнэ).
        return

    # Өмнөх хаалт дуусчихсан бол тоолуурыг тэгээс эхлүүлнэ.
    attempts = (0 if user.locked_until else user.failed_login_attempts) + 1
    user.failed_login_attempts = attempts
    user.locked_until = None
    if attempts >= max_login_attempts():
        user.locked_until = timezone.now() + timedelta(minutes=lockout_minutes())
    user.save(update_fields=["failed_login_attempts", "locked_until"])

    if not user.locked_until:
        return

    # Хаалтын мэдэгдэл нь нэвтрэх урсгалыг унагаах ёсгүй.
    try:
        from apps.notifications.services import send_account_locked_email

        send_account_locked_email(user, _issue_code(user))
    except Exception:  # noqa: BLE001
        logger.exception("Бүртгэл хаагдсан мэдэгдэл илгээхэд алдаа гарлаа: %s", user.email)


def clear_login_lock(user) -> None:
    """Тоолуур болон хаалтыг арилгана (амжилттай нэвтрэлт / нууц үг сэргээлт)."""
    if not user.failed_login_attempts and not user.locked_until:
        return
    user.failed_login_attempts = 0
    user.locked_until = None
    user.save(update_fields=["failed_login_attempts", "locked_until"])


def reset_password_with_code(email: str, code: str, new_password: str) -> None:
    """Validate the emailed code and set a new PIN.

    Raises django ValidationError on any problem (bad/expired code, bad PIN).
    """
    user = _active_user(email)

    record = None
    if user:
        record = (
            user.reset_codes.filter(code=code, used_at__isnull=True)
            .order_by("-created_at")
            .first()
        )
    if not record or not record.is_valid:
        raise ValidationError("Баталгаажуулах код буруу эсвэл хугацаа нь дууссан байна.")

    validate_password(new_password, user)  # enforces the 4-digit PIN format

    user.set_password(new_password)
    user.save(update_fields=["password"])

    # Burn this code and any other outstanding codes for the account.
    now = timezone.now()
    user.reset_codes.filter(used_at__isnull=True).update(used_at=now)

    # Хаагдсан бүртгэл нууц үгээ сэргээснээр шууд нээгдэнэ — хаалтын хугацаа
    # дуустал хүлээх шаардлагагүй.
    clear_login_lock(user)
