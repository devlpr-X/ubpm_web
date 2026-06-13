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
        MANAGER = "MANAGER", "Менежер"
        OPERATOR = "OPERATOR", "Оператор"
        CUSTOMER = "CUSTOMER", "Хэрэглэгч"

    username = None
    email = models.EmailField("Email", unique=True)
    phone = models.CharField("Утас", max_length=20, blank=True, db_index=True)
    full_name = models.CharField("Бүтэн нэр", max_length=200, blank=True)
    role = models.CharField("Роль", max_length=20, choices=Role.choices, default=Role.CUSTOMER)
    branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff",
        verbose_name="Салбар",
    )

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
        return self.role in {self.Role.ADMIN, self.Role.MANAGER, self.Role.OPERATOR}


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
