from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

from core.entities.base import PaginatedEntities
from core.entities.user import User
from core.schemas.users import UserOutDto
from core.services.users import UserService


def create_test_user(user_id=None, equestrian_id=None, username="testuser"):
    """Create a test user entity."""
    return User(
        id=user_id or uuid4(),
        equestrian_id=equestrian_id or uuid4(),
        username=username,
        password="hashed",
        first_name="Test",
        last_name="User",
        created_at=datetime.now(timezone.utc),
    )


def create_test_user_dto(user_id=None, equestrian_id=None, username="testuser"):
    """Create a test user DTO."""
    return UserOutDto(
        id=user_id or uuid4(),
        equestrian_id=equestrian_id or uuid4(),
        username=username,
        first_name="Test",
        last_name="User",
        created_at=datetime.now(timezone.utc),
        scopes=[],
    )


class TestUserServiceGetUsersPaginated:
    """Tests for UserService.get_users_paginated method."""

    async def test_returns_paginated_entities(self):
        """Test that method returns PaginatedEntities[UserOutDto]."""
        # Arrange
        test_user = create_test_user()
        mock_repository = AsyncMock()
        mock_repository.get_users_paginated.return_value = ([test_user], 1)

        service = UserService(repository=mock_repository)

        # Act
        result = await service.get_users_paginated()

        # Assert
        assert isinstance(result, PaginatedEntities)
        assert result.total == 1
        assert len(result.items) == 1
        assert isinstance(result.items[0], UserOutDto)
        assert result.items[0].id == test_user.id

    async def test_passes_filters_to_repository(self):
        """Test that filters are passed to repository."""
        # Arrange
        equestrian_id = uuid4()
        mock_repository = AsyncMock()
        mock_repository.get_users_paginated.return_value = ([], 0)

        service = UserService(repository=mock_repository)

        # Act
        await service.get_users_paginated(
            equestrian_ids=[equestrian_id],
            equestrian_service_keys=["service-key"],
            roles=["ADMIN"],
            limit=50,
            offset=10,
        )

        # Assert
        mock_repository.get_users_paginated.assert_called_once_with(
            equestrian_ids=[equestrian_id],
            equestrian_service_keys=["service-key"],
            roles=["ADMIN"],
            limit=50,
            offset=10,
        )

    async def test_converts_users_to_dtos(self):
        """Test that User entities are converted to UserOutDto."""
        # Arrange
        test_user1 = create_test_user(username="user1")
        test_user2 = create_test_user(username="user2")
        mock_repository = AsyncMock()
        mock_repository.get_users_paginated.return_value = ([test_user1, test_user2], 2)

        service = UserService(repository=mock_repository)

        # Act
        result = await service.get_users_paginated()

        # Assert
        assert len(result.items) == 2
        assert all(isinstance(item, UserOutDto) for item in result.items)
        assert result.items[0].username == "user1"
        assert result.items[1].username == "user2"

    async def test_empty_result(self):
        """Test with no matching users."""
        # Arrange
        mock_repository = AsyncMock()
        mock_repository.get_users_paginated.return_value = ([], 0)

        service = UserService(repository=mock_repository)

        # Act
        result = await service.get_users_paginated()

        # Assert
        assert result.total == 0
        assert len(result.items) == 0

    async def test_preserves_total_count(self):
        """Test that total count from repository is preserved."""
        # Arrange
        test_user = create_test_user()
        mock_repository = AsyncMock()
        mock_repository.get_users_paginated.return_value = ([test_user], 100)

        service = UserService(repository=mock_repository)

        # Act
        result = await service.get_users_paginated(limit=10, offset=0)

        # Assert
        assert (
            result.total == 100
        )  # Total is 100, but only 1 user returned due to pagination
        assert len(result.items) == 1

    async def test_default_pagination_values(self):
        """Test that default pagination values are used."""
        # Arrange
        mock_repository = AsyncMock()
        mock_repository.get_users_paginated.return_value = ([], 0)

        service = UserService(repository=mock_repository)

        # Act
        await service.get_users_paginated()

        # Assert
        mock_repository.get_users_paginated.assert_called_once_with(
            equestrian_ids=None,
            equestrian_service_keys=None,
            roles=None,
            limit=100,
            offset=0,
        )

    async def test_custom_pagination_values(self):
        """Test that custom pagination values are passed."""
        # Arrange
        mock_repository = AsyncMock()
        mock_repository.get_users_paginated.return_value = ([], 0)

        service = UserService(repository=mock_repository)

        # Act
        await service.get_users_paginated(limit=25, offset=50)

        # Assert
        mock_repository.get_users_paginated.assert_called_once_with(
            equestrian_ids=None,
            equestrian_service_keys=None,
            roles=None,
            limit=25,
            offset=50,
        )

    async def test_multiple_filters(self):
        """Test with multiple filters applied."""
        # Arrange
        equestrian_id1 = uuid4()
        equestrian_id2 = uuid4()
        mock_repository = AsyncMock()
        mock_repository.get_users_paginated.return_value = ([], 0)

        service = UserService(repository=mock_repository)

        # Act
        await service.get_users_paginated(
            equestrian_ids=[equestrian_id1, equestrian_id2],
            equestrian_service_keys=["key1", "key2"],
            roles=["ADMIN", "USER"],
        )

        # Assert
        mock_repository.get_users_paginated.assert_called_once_with(
            equestrian_ids=[equestrian_id1, equestrian_id2],
            equestrian_service_keys=["key1", "key2"],
            roles=["ADMIN", "USER"],
            limit=100,
            offset=0,
        )
