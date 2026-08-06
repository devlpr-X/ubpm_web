from django.conf import settings
from django.db import models


class SiteContent(models.Model):
    """Admin-editable content block for public pages (e.g. /about/).

    Looked up by a stable ``key``. ``body`` may contain simple HTML (it is
    rendered with |safe and only staff can edit it). A video can either be
    uploaded (stored via the configured storage / CDN) or referenced by an
    external embed URL.
    """

    key = models.SlugField("Түлхүүр", max_length=100, unique=True)
    title = models.CharField("Гарчиг", max_length=200, blank=True)
    body = models.TextField("Агуулга", blank=True)
    video = models.FileField(
        "Бичлэг (файл)", upload_to="site/videos/%Y/%m/", blank=True, null=True
    )
    video_url = models.URLField("Бичлэг (гадаад линк)", max_length=500, blank=True)
    link_label = models.CharField("Холбоос — нэр", max_length=200, blank=True)
    link_url = models.URLField("Холбоос — URL", max_length=500, blank=True)
    updated_at = models.DateTimeField("Шинэчилсэн", auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Шинэчилсэн хэрэглэгч",
    )

    class Meta:
        ordering = ["key"]
        verbose_name = "Сайтын агуулга"
        verbose_name_plural = "Сайтын агуулга"

    def __str__(self):
        return self.title or self.key

    @classmethod
    def get_block(
        cls, key, *, default_title="", default_body="", default_link_label="", default_link_url=""
    ):
        """Fetch the block for `key`, creating it with defaults on first use."""
        obj, _ = cls.objects.get_or_create(
            key=key,
            defaults={
                "title": default_title,
                "body": default_body,
                "link_label": default_link_label,
                "link_url": default_link_url,
            },
        )
        return obj

    @property
    def video_src(self):
        """Best available video source: uploaded file URL, else external URL."""
        if self.video:
            return self.video.url
        return self.video_url or ""
