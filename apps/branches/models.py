from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class Branch(models.Model):
    name = models.CharField("Нэр", max_length=200)
    code = models.SlugField("Код", max_length=50, unique=True, blank=True)
    address_line = models.CharField("Хаяг", max_length=500)
    city = models.CharField("Хот", max_length=100, default="Улаанбаатар")
    district = models.CharField("Дүүрэг", max_length=100, blank=True)
    latitude = models.DecimalField(
        "Latitude", max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        "Longitude", max_digits=9, decimal_places=6, null=True, blank=True
    )
    phones = models.JSONField("Утасны жагсаалт", default=list, blank=True)
    working_hours = models.CharField("Ажиллах цаг", max_length=200, default="10:00–17:30")
    is_active = models.BooleanField("Идэвхтэй", default=True)
    cover_image = models.ImageField(
        "Нүүр зураг", upload_to="branches/covers/%Y/%m/", null=True, blank=True
    )
    description = models.TextField("Тайлбар", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Салбар"
        verbose_name_plural = "Салбарууд"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.code:
            base = slugify(self.name) or "branch"
            code = base
            i = 2
            while Branch.objects.filter(code=code).exclude(pk=self.pk).exists():
                code = f"{base}-{i}"
                i += 1
            self.code = code
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("branches:detail", args=[self.code])


class PartnerLocation(models.Model):
    name = models.CharField("Нэр", max_length=200)
    partner_company = models.CharField("Хамтрагч компани", max_length=200, blank=True)
    address = models.CharField("Хаяг", max_length=500)
    phone = models.CharField("Утас", max_length=50, blank=True)
    notes = models.TextField("Тэмдэглэл", blank=True)
    is_active = models.BooleanField("Идэвхтэй", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Хамтрагч цэг"
        verbose_name_plural = "Хамтрагч цэгүүд"

    def __str__(self):
        return self.name


class BranchMedia(models.Model):
    class MediaType(models.TextChoices):
        IMAGE = "IMAGE", "Зураг"
        VIDEO = "VIDEO", "Бичлэг"

    branch = models.ForeignKey(
        Branch, on_delete=models.CASCADE, related_name="gallery", verbose_name="Салбар"
    )
    media_type = models.CharField(
        "Төрөл", max_length=10, choices=MediaType.choices, default=MediaType.IMAGE
    )
    file = models.FileField("Файл", upload_to="branches/gallery/%Y/%m/")
    caption = models.CharField("Тайлбар", max_length=300, blank=True)
    sort_order = models.PositiveIntegerField("Дараалал", default=0)

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = "Салбарын медиа"
        verbose_name_plural = "Салбарын медиа"

    def __str__(self):
        return f"{self.branch.name} — {self.get_media_type_display()}"
