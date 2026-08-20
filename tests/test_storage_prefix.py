"""R2 / S3 дээр хадгалагдах файлын зам "ubpm/" угтвартай байхыг шалгана.

Bucket-ийг өөр төслүүдтэй хуваан ашигладаг тул бүх файл (зураг, видео) bucket
доторх ubpm/ хавтаст орж, нийтийн URL нь ч мөн
``https://pub-….r2.dev/ubpm/devices/2026/08/…`` хэлбэртэй гарах ёстой.
"""

import importlib
import os
from unittest import mock

import pytest
from storages.backends.s3 import S3Storage

R2_ENV = {
    "R2_BUCKET": "electricletter-media",
    "R2_PUBLIC_URL": "https://pub-3fc924a3ab6c4c2e94ead457691d0588.r2.dev",
}


def _load_settings(**extra_env):
    with mock.patch.dict(os.environ, {**R2_ENV, **extra_env}, clear=False):
        base = importlib.import_module("ubpm.settings.base")
        return importlib.reload(base)


@pytest.fixture(autouse=True)
def _restore_settings_module():
    """Модулийг R2-гүй анхны төлөвт нь буцааж ачаална."""
    yield
    keys = dict.fromkeys((*R2_ENV, "R2_PREFIX"), "")
    with mock.patch.dict(os.environ, keys, clear=False):
        importlib.reload(importlib.import_module("ubpm.settings.base"))


def test_r2_uploads_get_the_ubpm_prefix_by_default():
    base = _load_settings()

    assert base.USE_S3 is True
    assert base.AWS_LOCATION == "ubpm"


def test_prefix_is_configurable_and_slashes_are_trimmed():
    assert _load_settings(R2_PREFIX="/staging/").AWS_LOCATION == "staging"


def test_public_url_includes_the_prefix():
    base = _load_settings()
    storage = S3Storage(
        bucket_name=base.AWS_STORAGE_BUCKET_NAME,
        custom_domain=base.AWS_S3_CUSTOM_DOMAIN,
        location=base.AWS_LOCATION,
        querystring_auth=False,
    )

    assert storage.url("devices/2026/08/phone.jpg") == (
        "https://pub-3fc924a3ab6c4c2e94ead457691d0588.r2.dev"
        "/ubpm/devices/2026/08/phone.jpg"
    )
