from unittest.mock import MagicMock, patch

import pytest

from core.exceptions.auth import InvalidServiceKey
from core.exceptions.base import ClientError
from depends.services import get_service_context, get_service_pagination_params


class TestGetServiceContext:
    """Tests for get_service_context dependency."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings with service_key configured."""
        mock = MagicMock()
        mock.service_key = "test-service-key"
        with patch("settings.settings", mock):
            yield mock

    async def test_valid_service_key(self, mock_settings):
        """Test with valid service key."""
        # Act
        result = await get_service_context(service_key="test-service-key")

        # Assert
        assert result is None

    async def test_invalid_service_key(self, mock_settings):
        """Test with invalid service key."""
        # Act & Assert
        with pytest.raises(InvalidServiceKey):
            await get_service_context(service_key="invalid-key")

    async def test_missing_service_key(self, mock_settings):
        """Test with missing service key."""
        # Act & Assert
        with pytest.raises(InvalidServiceKey):
            await get_service_context(service_key=None)

    async def test_empty_service_key(self, mock_settings):
        """Test with empty service key."""
        # Act & Assert
        with pytest.raises(InvalidServiceKey):
            await get_service_context(service_key="")

    async def test_whitespace_service_key(self, mock_settings):
        """Test with whitespace-only service key."""
        # Act & Assert
        with pytest.raises(InvalidServiceKey):
            await get_service_context(service_key="   ")

    async def test_service_key_not_configured(self):
        """Test when SERVICE_KEY is not configured in settings."""
        # Arrange
        mock = MagicMock()
        mock.service_key = None
        with patch("settings.settings", mock):
            # Act & Assert
            with pytest.raises(
                ClientError,
                match="Сервисные эндпоинты недоступны: SERVICE_KEY не настроен",
            ):
                await get_service_context(service_key="any-key")


class TestGetServicePaginationParams:
    """Tests for get_service_pagination_params dependency."""

    async def test_default_params(self):
        """Test with default pagination parameters."""
        # Act
        result = await get_service_pagination_params()

        # Assert
        assert result == {"limit": 100, "offset": 0}

    async def test_custom_params(self):
        """Test with custom pagination parameters."""
        # Act
        result = await get_service_pagination_params(limit=50, offset=10)

        # Assert
        assert result == {"limit": 50, "offset": 10}

    async def test_max_limit(self):
        """Test with maximum allowed limit."""
        # Act
        result = await get_service_pagination_params(limit=5000)

        # Assert
        assert result == {"limit": 5000, "offset": 0}

    async def test_limit_too_large(self):
        """Test with limit exceeding maximum."""
        # Act & Assert
        with pytest.raises(ClientError, match="limit не может превышать 5000"):
            await get_service_pagination_params(limit=5001)

    async def test_limit_zero(self):
        """Test with zero limit."""
        # Act & Assert
        with pytest.raises(ClientError, match="limit должен быть положительным числом"):
            await get_service_pagination_params(limit=0)

    async def test_limit_negative(self):
        """Test with negative limit."""
        # Act & Assert
        with pytest.raises(ClientError, match="limit должен быть положительным числом"):
            await get_service_pagination_params(limit=-1)

    async def test_offset_negative(self):
        """Test with negative offset."""
        # Act & Assert
        with pytest.raises(ClientError, match="offset не может быть отрицательным"):
            await get_service_pagination_params(offset=-1)

    async def test_offset_zero(self):
        """Test with zero offset."""
        # Act
        result = await get_service_pagination_params(offset=0)

        # Assert
        assert result == {"limit": 100, "offset": 0}

    async def test_large_offset(self):
        """Test with large offset."""
        # Act
        result = await get_service_pagination_params(offset=1000000)

        # Assert
        assert result == {"limit": 100, "offset": 1000000}
