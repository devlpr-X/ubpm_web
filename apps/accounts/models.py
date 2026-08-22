import math

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("Email шаардлагатай")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("role", User.Role.CUSTOMER)
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("role", User.Role.ADMIN)
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Админ"
        CUSTOMER = "CUSTOMER", "Хэрэглэгч"

    # Дотоод ажилтны role-ууд. Хянах самбар, staff API, хүсэлт хувиарлах сонголт
    # бүгд эндээс уншина — эрх нэмэх/хасах бол зөвхөн энэ мөрийг засна.
    STAFF_ROLES = frozenset({Role.ADMIN})

    class CustomerType(models.TextChoices):
        # Утгууд нь intake.IntakeRequest.CustomerType-тэй яг таарах ёстой
        # (профайл ↔ хүсэлтийн маягт хооронд шууд хуулагддаг). Тестээр хамгаалсан.
        INDIVIDUAL = "INDIVIDUAL", "Иргэн"
        COMPANY = "COMPANY", "Компани"

    username = None
    email = models.EmailField("Email", unique=True)
    phone = models.CharField("Утас", max_length=20, blank=True, db_index=True)
    full_name = models.CharField("Бүтэн нэр", max_length=200, blank=True)
    role = models.CharField("Роль", max_length=20, choices=Role.choices, default=Role.CUSTOMER)

    # --- Холбоо барих мэдээлэл ---
    # Хүсэлт илгээхэд эндээс маягт автоматаар дүүрч, илгээсний дараа шинэ утгууд
    # нь эргээд энд хадгалагдана (apps/accounts/contact.py).
    customer_type = models.CharField(
        "Хэрэглэгчийн төрөл",
        max_length=20,
        choices=CustomerType.choices,
        default=CustomerType.INDIVIDUAL,
    )
    company_name = models.CharField("Компанийн нэр", max_length=200, blank=True)
    city = models.CharField("Хот", max_length=100, blank=True)
    district = models.CharField("Дүүрэг", max_length=100, blank=True)
    address_line = models.CharField("Хаяг", max_length=500, blank=True)
    # Хамгийн сүүлд хүсэлт дээр газрын зургаас сонгосон очиж авах байршил.
    # Профайл дээр газрын зурагтай харагдаж, дараагийн хүсэлт дээр чагтлахад
    # шууд ашиглагдана (apps/accounts/contact.py).
    pickup_lat = models.DecimalField(
        "Байршил (өргөрөг)", max_digits=9, decimal_places=6, null=True, blank=True
    )
    pickup_lng = models.DecimalField(
        "Байршил (уртраг)", max_digits=9, decimal_places=6, null=True, blank=True
    )
    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff",
        verbose_name="Салбар",
    )

    # --- Нэвтрэх оролдлогын хамгаалалт ---
    # Дараалсан буруу оролдлогыг тоолж, хязгаараас хэтэрвэл бүртгэлийг түр
    # хаана. Хаагдсан үед зөв нууц үг ч ажиллахгүй (backends.py), харин и-мэйл
    # рүү ирсэн кодоор нууц үгээ сэргээвэл шууд нээгдэнэ (services.py).
    failed_login_attempts = models.PositiveSmallIntegerField(
        "Амжилтгүй оролдлого", default=0
    )
    locked_until = models.DateTimeField("Хаалт дуусах", null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        ordering = ["email"]
        verbose_name = "Хэрэглэгч"
        verbose_name_plural = "Хэрэглэгчид"

    def __str__(self):
        return self.full_name or self.email

    @property
    def is_staff_role(self):
        return self.role in self.STAFF_ROLES

    @property
    def has_pickup_location(self):
        """Профайлд газрын зургийн байршил хадгалагдсан эсэх."""
        return self.pickup_lat is not None and self.pickup_lng is not None

    @property
    def is_login_locked(self):
        """Хэт олон буруу оролдлогын улмаас нэвтрэх нь түр хаагдсан эсэх."""
        return bool(self.locked_until and timezone.now() < self.locked_until)

    @property
    def lockout_minutes_left(self):
        """Хаалт дуусахад үлдсэн минут (дээш нь бүхэлчилнэ)."""
        if not self.is_login_locked:
            return 0
        seconds = (self.locked_until - timezone.now()).total_seconds()
        return max(1, math.ceil(seconds / 60))


class PasswordResetCode(models.Model):
    """A one-time 4-digit code emailed to a user to reset their PIN."""

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="reset_codes", verbose_name="Хэрэглэгч"
    )
    code = models.CharField("Код", max_length=4)
    created_at = models.DateTimeField("Үүсгэсэн", auto_now_add=True)
    expires_at = models.DateTimeField("Дуусах хугацаа")
    used_at = models.DateTimeField("Ашигласан", null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Нууц үг сэргээх код"
        verbose_name_plural = "Нууц үг сэргээх кодууд"

    def __str__(self):
        return f"{self.user.email} — {self.code}"

    @property
    def is_valid(self):
        return self.used_at is None and timezone.now() < self.expires_at
