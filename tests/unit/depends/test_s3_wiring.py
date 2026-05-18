"""Unit tests for S3 wiring in depends/utils.py (UT-21 to UT-25)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from utils.media import S3MediaStorage, S3PhotoUrlBuilder

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers — patch settings with known S3 values
# ---------------------------------------------------------------------------


class FakeSettings:
    s3_endpoint_url = "http://fake-minio:9000"
    s3_access_key = "fakekey"
    s3_secret_key = "fakesecret"
    s3_bucket_name = "test-bucket"
    s3_public_endpoint_url = "http://localhost:9999"


class FakePhotoUrlBuilder:
    def build(self, filename: str) -> str:
        return f"http://localhost:9000/gallery/{filename}"


# ---------------------------------------------------------------------------
# UT-21: get_media_storage returns S3MediaStorage instance
# ---------------------------------------------------------------------------


async def test_ut21_get_media_storage_returns_s3_media_storage() -> None:
    with patch("depends.utils.settings", FakeSettings()):
        from depends.utils import get_media_storage

        result = await get_media_storage()

    assert isinstance(result, S3MediaStorage)


# ---------------------------------------------------------------------------
# UT-22: returned object has endpoint_url from settings
# ---------------------------------------------------------------------------


async def test_ut22_get_media_storage_endpoint_url_from_settings() -> None:
    fake = FakeSettings()
    with patch("depends.utils.settings", fake):
        from depends.utils import get_media_storage

        result = await get_media_storage()

    assert isinstance(result, S3MediaStorage)
    assert result.endpoint_url == fake.s3_endpoint_url


# ---------------------------------------------------------------------------
# UT-23: returned object has bucket_name from settings
# ---------------------------------------------------------------------------


async def test_ut23_get_media_storage_bucket_name_from_settings() -> None:
    fake = FakeSettings()
    with patch("depends.utils.settings", fake):
        from depends.utils import get_media_storage

        result = await get_media_storage()

    assert isinstance(result, S3MediaStorage)
    assert result.bucket_name == fake.s3_bucket_name


# ---------------------------------------------------------------------------
# UT-24: get_photo_url_builder returns S3PhotoUrlBuilder instance
# ---------------------------------------------------------------------------


async def test_ut24_get_photo_url_builder_returns_s3_photo_url_builder() -> None:
    with patch("depends.utils.settings", FakeSettings()):
        from depends.utils import get_photo_url_builder

        result = await get_photo_url_builder()

    assert isinstance(result, S3PhotoUrlBuilder)


# ---------------------------------------------------------------------------
# UT-25: returned builder has public_endpoint_url from settings
# ---------------------------------------------------------------------------


async def test_ut25_get_photo_url_builder_public_endpoint_from_settings() -> None:
    fake = FakeSettings()
    with patch("depends.utils.settings", fake):
        from depends.utils import get_photo_url_builder

        result = await get_photo_url_builder()

    assert isinstance(result, S3PhotoUrlBuilder)
    assert result.public_endpoint_url == fake.s3_public_endpoint_url.rstrip("/")


async def test_get_horse_repository_wires_photo_url_builder() -> None:
    from depends.repositories import get_horse_repository
    from repositories.horse_repository import HorseRepository

    builder = FakePhotoUrlBuilder()
    result = await get_horse_repository(
        session=object(),  # type: ignore[arg-type]
        photo_url_builder=builder,
    )

    assert isinstance(result, HorseRepository)
    assert result.photo_url_builder is builder
