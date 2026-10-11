from django.db import models

from .validators import normalize_iban, validate_iban


class IBANField(models.CharField):
    """IBAN — хадгалахаас өмнө зай, зураасыг авч том үсэг болгоно (форм, admin)."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("max_length", 34)
        kwargs.setdefault("blank", True)
        kwargs.setdefault("validators", [validate_iban])
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        kwargs.pop("validators", None)
        return name, path, args, kwargs

    def to_python(self, value):
        value = super().to_python(value)
        return normalize_iban(value) if value else value
