"""Unit tests for S3MediaStorage, S3PhotoUrlBuilder (UT-01 to UT-20)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from botocore.config import Config

from utils.media import S3MediaStorage, S3PhotoUrlBuilder, _s3_client_config

# Only async tests use @pytest.mark.asyncio; sync tests (UT-16..UT-20) do not.

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ENDPOINT = "http://minio:9000"
ACCESS_KEY = "testkey"
SECRET_KEY = "testsecret"
BUCKET = "gallery"


def make_storage(bucket: str = BUCKET) -> S3MediaStorage:
    return S3MediaStorage(
        endpoint_url=ENDPOINT,
        access_key=ACCESS_KEY,
        secret_key=SECRET_KEY,
        bucket_name=bucket,
    )


def _make_s3_client_mock(
    put_object: AsyncMock | None = None,
    get_object: AsyncMock | None = None,
    delete_object: AsyncMock | None = None,
    body_content: bytes = b"data",
) -> MagicMock:
    """Build a mock s3 client context manager."""
    s3 = AsyncMock()
    if put_object is not None:
        s3.put_object = put_object
    else:
        s3.put_object = AsyncMock(return_value={})

    if get_object is not None:
        s3.get_object = get_object
    else:
        body_mock = AsyncMock()
        body_mock.read = AsyncMock(return_value=body_content)
        s3.get_object = AsyncMock(return_value={"Body": body_mock})

    if delete_object is not None:
        s3.delete_object = delete_object
    else:
        s3.delete_object = AsyncMock(return_value={})

    return s3


def _patch_aioboto3(s3_client_mock: MagicMock) -> Any:
    """Return a patch context that replaces aioboto3.Session().client(...)."""
    session_mock = MagicMock()

    @asynccontextmanager
    async def fake_client(*args: Any, **kwargs: Any):  # type: ignore[misc]
        yield s3_client_mock

    session_mock.client = fake_client
    return patch("aioboto3.Session", return_value=session_mock)


# ---------------------------------------------------------------------------
# UT-01: save — put_object called with correct bucket, key, body
# ---------------------------------------------------------------------------


async def test_ut01_save_calls_put_object_with_correct_args() -> None:
    s3 = _make_s3_client_mock()
    storage = make_storage()

    with _patch_aioboto3(s3):
        await storage.save(b"content", "photo.jpg")

    s3.put_object.assert_awaited_once_with(
        Bucket=BUCKET,
        Key="photo.jpg",
        Body=b"content",
    )


# ---------------------------------------------------------------------------
# UT-02: save — returns filename unchanged
# ---------------------------------------------------------------------------


async def test_ut02_save_returns_filename_unchanged() -> None:
    s3 = _make_s3_client_mock()
    storage = make_storage()

    with _patch_aioboto3(s3):
        result = await storage.save(b"bytes", "my-file.png")

    assert result == "my-file.png"


# ---------------------------------------------------------------------------
# UT-03: save — empty filename: put_object called with empty key
# ---------------------------------------------------------------------------


async def test_ut03_save_empty_filename_calls_put_object_with_empty_key() -> None:
    s3 = _make_s3_client_mock()
    storage = make_storage()

    with _patch_aioboto3(s3):
        await storage.save(b"bytes", "")

    s3.put_object.assert_awaited_once_with(Bucket=BUCKET, Key="", Body=b"bytes")


# ---------------------------------------------------------------------------
# UT-04: save — S3 ClientError propagates
# ---------------------------------------------------------------------------


async def test_ut04_save_propagates_s3_client_error() -> None:
    s3_error = AsyncMock(side_effect=Exception("S3 ClientError"))
    s3 = _make_s3_client_mock(put_object=s3_error)
    storage = make_storage()

    with _patch_aioboto3(s3):
        with pytest.raises(Exception, match="S3 ClientError"):
            await storage.save(b"bytes", "file.jpg")


# ---------------------------------------------------------------------------
# UT-05: save — connection error propagates (not suppressed)
# ---------------------------------------------------------------------------


async def test_ut05_save_connection_error_not_suppressed() -> None:
    s3_error = AsyncMock(side_effect=ConnectionError("endpoint unreachable"))
    s3 = _make_s3_client_mock(put_object=s3_error)
    storage = make_storage()

    with _patch_aioboto3(s3):
        with pytest.raises(ConnectionError):
            await storage.save(b"bytes", "file.jpg")


# ---------------------------------------------------------------------------
# UT-06: load — returns bytes from body
# ---------------------------------------------------------------------------


async def test_ut06_load_returns_bytes_and_calls_get_object() -> None:
    s3 = _make_s3_client_mock(body_content=b"image-bytes")
    storage = make_storage()

    with _patch_aioboto3(s3):
        result = await storage.load("photo.jpg")

    assert result == b"image-bytes"
    s3.get_object.assert_awaited_once_with(Bucket=BUCKET, Key="photo.jpg")


# ---------------------------------------------------------------------------
# UT-07: load — NoSuchKey error propagates
# ---------------------------------------------------------------------------


async def test_ut07_load_no_such_key_propagates() -> None:
    no_such_key = AsyncMock(side_effect=Exception("NoSuchKey"))
    s3 = _make_s3_client_mock(get_object=no_such_key)
    storage = make_storage()

    with _patch_aioboto3(s3):
        with pytest.raises(Exception, match="NoSuchKey"):
            await storage.load("missing.jpg")


# ---------------------------------------------------------------------------
# UT-08: load — connection error propagates
# ---------------------------------------------------------------------------


async def test_ut08_load_connection_error_not_suppressed() -> None:
    conn_error = AsyncMock(side_effect=ConnectionError("unreachable"))
    s3 = _make_s3_client_mock(get_object=conn_error)
    storage = make_storage()

    with _patch_aioboto3(s3):
        with pytest.raises(ConnectionError):
            await storage.load("file.jpg")


# ---------------------------------------------------------------------------
# UT-09: load — empty filename: get_object called with empty key
# ---------------------------------------------------------------------------


async def test_ut09_load_empty_filename_calls_get_object_with_empty_key() -> None:
    s3 = _make_s3_client_mock(body_content=b"")
    storage = make_storage()

    with _patch_aioboto3(s3):
        result = await storage.load("")

    s3.get_object.assert_awaited_once_with(Bucket=BUCKET, Key="")
    assert result == b""


# ---------------------------------------------------------------------------
# UT-10: delete — delete_object called with correct bucket and key
# ---------------------------------------------------------------------------


async def test_ut10_delete_calls_delete_object_with_correct_args() -> None:
    s3 = _make_s3_client_mock()
    storage = make_storage()

    with _patch_aioboto3(s3):
        await storage.delete("photo.jpg")

    s3.delete_object.assert_awaited_once_with(Bucket=BUCKET, Key="photo.jpg")


# ---------------------------------------------------------------------------
# UT-11: delete — ClientError propagates
# ---------------------------------------------------------------------------


async def test_ut11_delete_propagates_client_error() -> None:
    err = AsyncMock(side_effect=Exception("ClientError: access denied"))
    s3 = _make_s3_client_mock(delete_object=err)
    storage = make_storage()

    with _patch_aioboto3(s3):
        with pytest.raises(Exception, match="ClientError"):
            await storage.delete("photo.jpg")


# ---------------------------------------------------------------------------
# UT-12: delete — non-existent object: S3 returns success (idempotent)
# ---------------------------------------------------------------------------


async def test_ut12_delete_nonexistent_object_completes_without_exception() -> None:
    # S3 delete_object returns 204/success even for missing objects
    s3 = _make_s3_client_mock()
    storage = make_storage()

    with _patch_aioboto3(s3):
        # Should not raise
        await storage.delete("nonexistent.jpg")

    s3.delete_object.assert_awaited_once()


# ---------------------------------------------------------------------------
# UT-13: delete — connection error propagates
# ---------------------------------------------------------------------------


async def test_ut13_delete_connection_error_not_suppressed() -> None:
    conn_error = AsyncMock(side_effect=ConnectionError("minio down"))
    s3 = _make_s3_client_mock(delete_object=conn_error)
    storage = make_storage()

    with _patch_aioboto3(s3):
        with pytest.raises(ConnectionError):
            await storage.delete("file.jpg")


# ---------------------------------------------------------------------------
# UT-14: S3MediaStorage — credentials from constructor passed to boto3 client
# ---------------------------------------------------------------------------


async def test_ut14_constructor_credentials_passed_to_boto3() -> None:
    captured_kwargs: dict[str, Any] = {}
    session_mock = MagicMock()

    @asynccontextmanager
    async def capturing_client(*args: Any, **kwargs: Any):  # type: ignore[misc]
        captured_kwargs.update(kwargs)
        s3 = AsyncMock()
        s3.put_object = AsyncMock(return_value={})
        yield s3

    session_mock.client = capturing_client

    storage = S3MediaStorage(
        endpoint_url="http://custom:9000",
        access_key="mykey",
        secret_key="mysecret",
        bucket_name="mybucket",
    )

    with patch("aioboto3.Session", return_value=session_mock):
        await storage.save(b"data", "file.jpg")

    assert captured_kwargs["endpoint_url"] == "http://custom:9000"
    assert captured_kwargs["aws_access_key_id"] == "mykey"
    assert captured_kwargs["aws_secret_access_key"] == "mysecret"
    config = captured_kwargs["config"]
    assert isinstance(config, Config)
    assert config.request_checksum_calculation == "when_required"
    assert config.response_checksum_validation == "when_required"


# ---------------------------------------------------------------------------
# UT-S3FIX: checksum config for S3-compatible providers (Beget, MinIO)
# ---------------------------------------------------------------------------


def test_ut_s3fix_s3_client_config_when_required() -> None:
    config = _s3_client_config()
    assert config.request_checksum_calculation == "when_required"
    assert config.response_checksum_validation == "when_required"
    assert _s3_client_config() is not config


async def test_ut_s3fix_load_passes_checksum_config() -> None:
    captured_kwargs: dict[str, Any] = {}
    session_mock = MagicMock()

    @asynccontextmanager
    async def capturing_client(*args: Any, **kwargs: Any):  # type: ignore[misc]
        captured_kwargs.update(kwargs)
        s3 = _make_s3_client_mock(body_content=b"x")
        yield s3

    session_mock.client = capturing_client
    storage = make_storage()

    with patch("aioboto3.Session", return_value=session_mock):
        await storage.load("f.jpg")

    assert captured_kwargs["config"].request_checksum_calculation == "when_required"


async def test_ut_s3fix_delete_passes_checksum_config() -> None:
    captured_kwargs: dict[str, Any] = {}
    session_mock = MagicMock()

    @asynccontextmanager
    async def capturing_client(*args: Any, **kwargs: Any):  # type: ignore[misc]
        captured_kwargs.update(kwargs)
        s3 = _make_s3_client_mock()
        yield s3

    session_mock.client = capturing_client
    storage = make_storage()

    with patch("aioboto3.Session", return_value=session_mock):
        await storage.delete("f.jpg")

    assert captured_kwargs["config"].response_checksum_validation == "when_required"


# ---------------------------------------------------------------------------
# UT-15: S3MediaStorage — bucket_name from constructor used in all operations
# ---------------------------------------------------------------------------


async def test_ut15_bucket_name_from_constructor_used_in_all_operations() -> None:
    custom_bucket = "custom-bucket"
    s3 = _make_s3_client_mock(body_content=b"data")
    storage = make_storage(bucket=custom_bucket)

    with _patch_aioboto3(s3):
        await storage.save(b"data", "f.jpg")
        await storage.load("f.jpg")
        await storage.delete("f.jpg")

    s3.put_object.assert_awaited_once_with(
        Bucket=custom_bucket, Key="f.jpg", Body=b"data"
    )
    s3.get_object.assert_awaited_once_with(Bucket=custom_bucket, Key="f.jpg")
    s3.delete_object.assert_awaited_once_with(Bucket=custom_bucket, Key="f.jpg")


# ---------------------------------------------------------------------------
# UT-16: S3PhotoUrlBuilder — builds URL as <endpoint>/<bucket>/<filename>
# ---------------------------------------------------------------------------


def test_ut16_url_builder_standard_filename() -> None:
    builder = S3PhotoUrlBuilder(
        public_endpoint_url="http://localhost:9000", bucket_name="gallery"
    )
    url = builder.build("abc123.jpg")
    assert url == "http://localhost:9000/gallery/abc123.jpg"


# ---------------------------------------------------------------------------
# UT-17: trailing slash in endpoint is normalised
# ---------------------------------------------------------------------------


def test_ut17_url_builder_trailing_slash_normalised() -> None:
    builder = S3PhotoUrlBuilder(
        public_endpoint_url="http://localhost:9000/", bucket_name="gallery"
    )
    url = builder.build("img.png")
    assert url == "http://localhost:9000/gallery/img.png"
    assert "//" not in url.split("://", 1)[1]


# ---------------------------------------------------------------------------
# UT-18: empty filename does not crash
# ---------------------------------------------------------------------------


def test_ut18_url_builder_empty_filename_does_not_crash() -> None:
    builder = S3PhotoUrlBuilder(
        public_endpoint_url="http://localhost:9000", bucket_name="gallery"
    )
    url = builder.build("")
    assert url == "http://localhost:9000/gallery/"


# ---------------------------------------------------------------------------
# UT-19: filename with spaces/special chars: raw concatenation, no URL encoding
# ---------------------------------------------------------------------------


def test_ut19_url_builder_special_chars_not_encoded() -> None:
    builder = S3PhotoUrlBuilder(
        public_endpoint_url="http://localhost:9000", bucket_name="gallery"
    )
    url = builder.build("my file (1).jpg")
    assert url == "http://localhost:9000/gallery/my file (1).jpg"


# ---------------------------------------------------------------------------
# UT-20: different bucket_name → different URLs
# ---------------------------------------------------------------------------


def test_ut_s3fix_url_builder_subdomain_without_bucket_in_path() -> None:
    builder = S3PhotoUrlBuilder(
        public_endpoint_url="https://cloud.eqcms.ru",
        bucket_name="165bf68155be-eqcms",
        include_bucket_in_path=False,
    )
    url = builder.build("abc123.jpg")
    assert url == "https://cloud.eqcms.ru/abc123.jpg"


def test_ut20_different_bucket_names_produce_different_urls() -> None:
    b1 = S3PhotoUrlBuilder(
        public_endpoint_url="http://localhost:9000", bucket_name="gallery"
    )
    b2 = S3PhotoUrlBuilder(
        public_endpoint_url="http://localhost:9000", bucket_name="other-bucket"
    )
    assert b1.build("img.jpg") != b2.build("img.jpg")
    assert "gallery" in b1.build("img.jpg")
    assert "other-bucket" in b2.build("img.jpg")
