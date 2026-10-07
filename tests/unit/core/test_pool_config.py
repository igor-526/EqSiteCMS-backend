"""Unit tests for database connection pool configuration."""

import os
from unittest.mock import patch

import pytest

from settings import Settings


class TestPoolConfigDefaults:
    """Test default values for pool configuration."""

    def test_default_pool_size(self):
        """DB_POOL_SIZE defaults to 20."""
        settings = Settings()
        assert settings.db_pool_size == 20

    def test_default_max_overflow(self):
        """DB_MAX_OVERFLOW defaults to 10."""
        settings = Settings()
        assert settings.db_max_overflow == 10

    def test_default_pool_timeout(self):
        """DB_POOL_TIMEOUT defaults to 30."""
        settings = Settings()
        assert settings.db_pool_timeout == 30

    def test_default_pool_recycle(self):
        """DB_POOL_RECYCLE defaults to 3600."""
        settings = Settings()
        assert settings.db_pool_recycle == 3600


class TestPoolConfigEnvironmentVariables:
    """Test pool configuration via environment variables."""

    def test_custom_pool_size_via_env(self):
        """DB_POOL_SIZE can be overridden via environment variable."""
        with patch.dict(os.environ, {"DB_POOL_SIZE": "50"}):
            settings = Settings()
            assert settings.db_pool_size == 50

    def test_custom_max_overflow_via_env(self):
        """DB_MAX_OVERFLOW can be overridden via environment variable."""
        with patch.dict(os.environ, {"DB_MAX_OVERFLOW": "20"}):
            settings = Settings()
            assert settings.db_max_overflow == 20

    def test_custom_pool_timeout_via_env(self):
        """DB_POOL_TIMEOUT can be overridden via environment variable."""
        with patch.dict(os.environ, {"DB_POOL_TIMEOUT": "60"}):
            settings = Settings()
            assert settings.db_pool_timeout == 60

    def test_custom_pool_recycle_via_env(self):
        """DB_POOL_RECYCLE can be overridden via environment variable."""
        with patch.dict(os.environ, {"DB_POOL_RECYCLE": "7200"}):
            settings = Settings()
            assert settings.db_pool_recycle == 7200

    def test_multiple_pool_config_via_env(self):
        """Multiple pool parameters can be configured simultaneously."""
        with patch.dict(
            os.environ,
            {
                "DB_POOL_SIZE": "30",
                "DB_MAX_OVERFLOW": "15",
                "DB_POOL_TIMEOUT": "45",
                "DB_POOL_RECYCLE": "1800",
            },
        ):
            settings = Settings()
            assert settings.db_pool_size == 30
            assert settings.db_max_overflow == 15
            assert settings.db_pool_timeout == 45
            assert settings.db_pool_recycle == 1800


class TestPoolConfigValidation:
    """Test validation constraints for pool configuration."""

    def test_pool_size_must_be_positive(self):
        """DB_POOL_SIZE must be >= 1."""
        with patch.dict(os.environ, {"DB_POOL_SIZE": "0"}):
            with pytest.raises(ValueError):
                Settings()

    def test_max_overflow_must_be_non_negative(self):
        """DB_MAX_OVERFLOW must be >= 0."""
        with patch.dict(os.environ, {"DB_MAX_OVERFLOW": "-1"}):
            with pytest.raises(ValueError):
                Settings()

    def test_pool_timeout_must_be_positive(self):
        """DB_POOL_TIMEOUT must be >= 1."""
        with patch.dict(os.environ, {"DB_POOL_TIMEOUT": "0"}):
            with pytest.raises(ValueError):
                Settings()

    def test_pool_recycle_must_be_positive(self):
        """DB_POOL_RECYCLE must be >= 1."""
        with patch.dict(os.environ, {"DB_POOL_RECYCLE": "0"}):
            with pytest.raises(ValueError):
                Settings()
