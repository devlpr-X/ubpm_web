"""Password validation: accounts use a simple 4-digit numeric PIN.

The data behind these accounts is not sensitive, so instead of a long password
we use a fixed 4-digit PIN everywhere (web + mobile app + API).
"""

import re

from django.core.exceptions import ValidationError

PIN_RE = re.compile(r"^\d{4}$")


class FourDigitPinValidator:
    """Require the password to be exactly 4 digits (e.g. 1234)."""

    message = "Нууц үг яг 4 оронтой тоо байх ёстой (ж: 1234)."
    code = "invalid_pin"

    def validate(self, password, user=None):
        if not PIN_RE.fullmatch(password or ""):
            raise ValidationError(self.message, code=self.code)

    def get_help_text(self):
        return "Нууц үг яг 4 оронтой тоо (ж: 1234) байна."
