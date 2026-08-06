import secrets
import uuid

from django.conf import settings
from django.db import models
from django.urls import reverse


class DeviceCategory(models.Model):
    name = models.CharField("Нэр", max_length=100)
    slug = models.SlugField("Slug", max_length=100, unique=True)
    icon = models.CharField("Дүрс/Emoji", max_length=50, blank=True)
    is_active = models.BooleanField("Идэвхтэй", default=True)
    sort_order = models.PositiveIntegerField("Дараалал", default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = "Төхөөрөмжийн ангилал"
        verbose_name_plural = "Төхөөрөмжийн ангилалууд"

    def __str__(self):
        return self.name


def _gen_request_code():
    return f"REQ-{secrets.token_hex(4).upper()}"


class IntakeRequest(models.Model):
    class CustomerType(models.TextChoices):
        INDIVIDUAL = "INDIVIDUAL", "Иргэн"
        COMPANY = "COMPANY", "Компани"

    class RequestType(models.TextChoices):
        WORKING = "WORKING", "Ажиллагаатай утас"
        BROKEN = "BROKEN", "Эвдэрсэн / бусад төхөөрөмж"

    class Source(models.TextChoices):
        WEB = "WEB", "Вэб"
        APP = "APP", "Гар утасны апп"
        PHONE_CALL = "PHONE_CALL", "Утсаар"
        FB = "FB", "Facebook"
        WALKIN = "WALKIN", "Биеэр"

    class Status(models.TextChoices):
        NEW = "NEW", "Шинэ"
        PRICE_SENT = "PRICE_SENT", "Үнэ илгээсэн"
        APPROVED = "APPROVED", "Зөвшөөрсөн"
        PURCHASED = "PURCHASED", "Худалдан авсан"
        CANCELLED = "CANCELLED", "Цуцалсан"

    OPEN_STATUSES = {Status.NEW, Status.PRICE_SENT, Status.APPROVED}

    request_code = models.CharField(
        "Хүсэлтийн код", max_length=20, unique=True, default=_gen_request_code, db_index=True
    )
    tracking_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submitted_requests",
        verbose_name="Илгээсэн хэрэглэгч",
    )
    request_type = models.CharField(
        "Хүсэлтийн төрөл",
        max_length=20,
        choices=RequestType.choices,
        default=RequestType.BROKEN,
    )
    customer_type = models.CharField(
        "Хэрэглэгчийн төрөл",
        max_length=20,
        choices=CustomerType.choices,
        default=CustomerType.INDIVIDUAL,
    )
    contact_name = models.CharField("Холбоо барих нэр", max_length=200)
    company_name = models.CharField("Компанийн нэр", max_length=200, blank=True)
    contact_phone = models.CharField("Утас", max_length=20)
    contact_email = models.EmailField("Email", blank=True)
    city = models.CharField("Хот", max_length=100, default="Улаанбаатар")
    district = models.CharField("Дүүрэг", max_length=100, blank=True)
    address_line = models.CharField("Хаяг", max_length=500, blank=True)

    preferred_branch = models.ForeignKey(
        "branches.Branch",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="preferred_requests",
        verbose_name="Сонгосон салбар",
    )
    expected_price = models.DecimalField(
        "Хүсэж буй үнэ", max_digits=12, decimal_places=2, null=True, blank=True
    )
    pickup_required = models.BooleanField("Pickup хэрэгтэй", default=False)
    # Хүргэлтээр авах үед хэрэглэгчийн газрын зураг дээр сонгосон байршил.
    pickup_lat = models.DecimalField(
        "Байршил (өргөрөг)", max_digits=9, decimal_places=6, null=True, blank=True
    )
    pickup_lng = models.DecimalField(
        "Байршил (уртраг)", max_digits=9, decimal_places=6, null=True, blank=True
    )
    source = models.CharField(
        "Эх сурвалж", max_length=20, choices=Source.choices, default=Source.WEB
    )

    status = models.CharField(
        "Статус", max_length=20, choices=Status.choices, default=Status.NEW, db_index=True
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_requests",
        verbose_name="Хариуцсан оператор",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Хүсэлт"
        verbose_name_plural = "Хүсэлтүүд"

    def __str__(self):
        return f"{self.request_code} — {self.contact_name}"

    def get_absolute_url(self):
        return reverse("dashboard:request_detail", args=[self.request_code])

    def public_tracking_url(self):
        return reverse("intake:track_detail", args=[str(self.tracking_token)])

    @property
    def is_open(self):
        return self.status in self.OPEN_STATUSES

    @property
    def has_location(self):
        return self.pickup_lat is not None and self.pickup_lng is not None

    @property
    def total_quantity(self):
        return sum(item.quantity for item in self.items.all())


class DeviceItem(models.Model):
    class PowerStatus(models.TextChoices):
        YES = "YES", "Асна"
        NO = "NO", "Асахгүй"
        UNKNOWN = "UNKNOWN", "Мэдэхгүй"

    class ScreenStatus(models.TextChoices):
        OK = "OK", "Бүтэн"
        CRACKED = "CRACKED", "Хагарсан"
        BROKEN = "BROKEN", "Эвдэрсэн"
        DEAD = "DEAD", "Гэрэлтэхгүй"

    class BatteryStatus(models.TextChoices):
        OK = "OK", "Хэвийн"
        WEAK = "WEAK", "Сул"
        DEAD = "DEAD", "Үхсэн"
        UNKNOWN = "UNKNOWN", "Мэдэхгүй"

    class BodyStatus(models.TextChoices):
        OK = "OK", "Цэвэр"
        SCRATCHED = "SCRATCHED", "Зурагдсан"
        BROKEN = "BROKEN", "Хугарсан"

    class Grade(models.TextChoices):
        A = "A", "A — Маш сайн"
        B = "B", "B — Сайн"
        C = "C", "C — Дунд"
        D = "D", "D — Муу"

    intake_request = models.ForeignKey(
        IntakeRequest, on_delete=models.CASCADE, related_name="items", verbose_name="Хүсэлт"
    )
    category = models.ForeignKey(
        DeviceCategory, on_delete=models.PROTECT, related_name="items", verbose_name="Ангилал"
    )
    brand = models.CharField("Бренд", max_length=100, blank=True)
    model = models.CharField("Модель", max_length=200, blank=True)
    quantity = models.PositiveIntegerField("Тоо ширхэг", default=1)
    storage = models.CharField("Багтаамж", max_length=50, blank=True)
    color = models.CharField("Өнгө", max_length=50, blank=True)
    imei_or_serial = models.CharField("IMEI / Сериал", max_length=100, blank=True)

    power_on_status = models.CharField(
        "Асах эсэх",
        max_length=10,
        choices=PowerStatus.choices,
        default=PowerStatus.UNKNOWN,
    )
    screen_status = models.CharField(
        "Дэлгэцийн төлөв",
        max_length=10,
        choices=ScreenStatus.choices,
        default=ScreenStatus.OK,
    )
    battery_status = models.CharField(
        "Батарей",
        max_length=10,
        choices=BatteryStatus.choices,
        default=BatteryStatus.UNKNOWN,
    )
    body_status = models.CharField(
        "Биеийн төлөв",
        max_length=10,
        choices=BodyStatus.choices,
        default=BodyStatus.OK,
    )
    water_damage = models.BooleanField("Ус орсон", default=False)
    accessories = models.CharField("Дагалдах", max_length=300, blank=True)
    issue_description = models.TextField("Гэмтлийн тайлбар", blank=True)
    condition_grade = models.CharField(
        "Үнэлгээний зэрэг", max_length=2, choices=Grade.choices, blank=True
    )

    class Meta:
        ordering = ["id"]
        verbose_name = "Төхөөрөмж"
        verbose_name_plural = "Төхөөрөмжүүд"

    def __str__(self):
        label = f"{self.brand} {self.model}".strip()
        return label or self.category.name


class DeviceImage(models.Model):
    device_item = models.ForeignKey(
        DeviceItem, on_delete=models.CASCADE, related_name="images", verbose_name="Төхөөрөмж"
    )
    image = models.ImageField("Зураг", upload_to="devices/%Y/%m/")
    sort_order = models.PositiveIntegerField("Дараалал", default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = "Төхөөрөмжийн зураг"
        verbose_name_plural = "Төхөөрөмжийн зураг"

    def __str__(self):
        return f"Image #{self.pk} for {self.device_item}"
