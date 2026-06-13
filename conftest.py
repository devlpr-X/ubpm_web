"""Pytest configuration.

Force local filesystem storage (in an isolated temp dir) during tests so
uploads never touch the configured Cloudflare R2 / S3 bucket. FileSystemStorage
(not InMemoryStorage) is used because some tests rely on ``FieldFile.path``.
"""

import pytest


@pytest.fixture(autouse=True)
def _use_local_storage(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path / "media")
    settings.STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
