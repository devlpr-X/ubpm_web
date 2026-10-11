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


# IBAN: улсын код + 2 шалгах орон + дансны хэсэг. Монголынх (MN) нийт 20 тэмдэгт —
# MN + 2 шалгах + 4 банкны код + 12 оронтой данс.
IBAN_RE = re.compile(r"^[A-Z]{2}\d{2}[A-Z0-9]{8,30}$")
IBAN_LENGTHS = {"MN": 20}


def normalize_iban(value):
    """Хоосон зай, зураасыг авч том үсэг болгоно ("mn12 0005 ..." → "MN120005...")."""
    return re.sub(r"[\s-]", "", value or "").upper()


def validate_iban(value):
    """IBAN-ы хэлбэр, урт, mod-97 шалгах оронг шалгана (хоосон бол алгасна)."""
    iban = normalize_iban(value)
    if not iban:
        return
    message = "IBAN буруу байна (ж: MN12 0005 0050 1234 5678)."
    if not IBAN_RE.fullmatch(iban):
        raise ValidationError(message, code="invalid_iban")
    expected = IBAN_LENGTHS.get(iban[:2])
    if expected and len(iban) != expected:
        raise ValidationError(f"{iban[:2]} IBAN яг {expected} тэмдэгт байна.", code="invalid_iban")
    digits = "".join(str(int(ch, 36)) for ch in iban[4:] + iban[:4])
    if int(digits) % 97 != 1:
        raise ValidationError(message, code="invalid_iban")
