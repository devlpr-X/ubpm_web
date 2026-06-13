"""Password-reset-by-email-code logic, shared by the web views and the API."""

import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import PasswordResetCode, User


def _ttl():
    minutes = getattr(settings, "PASSWORD_RESET_CODE_TTL_MINUTES", 15)
    return timedelta(minutes=minutes)


def generate_code() -> str:
    """A random 4-digit code, zero-padded (e.g. '0421')."""
    return f"{secrets.randbelow(10000):04d}"


def send_reset_code(email: str) -> bool:
    """Create a reset code for the account and email it.

    Returns True if a code was sent. Always behaves the same to the caller to
    avoid leaking whether an email is registered.
    """
    email = (email or "").lower().strip()
    user = User.objects.filter(email__iexact=email, is_active=True).first()
    if not user:
        return False

    code = generate_code()
    PasswordResetCode.objects.create(
        user=user, code=code, expires_at=timezone.now() + _ttl()
    )

    # Local import avoids a circular import at module load time.
    from apps.notifications.services import send_password_reset_code_email

    send_password_reset_code_email(user, code)
    return True


def reset_password_with_code(email: str, code: str, new_password: str) -> None:
    """Validate the emailed code and set a new PIN.

    Raises django ValidationError on any problem (bad/expired code, bad PIN).
    """
    email = (email or "").lower().strip()
    user = User.objects.filter(email__iexact=email, is_active=True).first()

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
