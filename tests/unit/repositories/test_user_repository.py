from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.dialects import postgresql

from core.entities.user import User
from repositories.user_repository import UserRepository


class FakeExecuteResult:
    def __init__(self, rows=None, total=0):
        self._rows = rows or []
        self._total = total

    def mappings(self):
        return self

    def all(self):
        return self._rows

    def scalar(self):
        return self._total

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None


class FakeAsyncSession:
    def __init__(self, rows=None, total=0):
        self.statements = []
        self._rows = rows or []
        self._total = total

    async def execute(self, statement):
        self.statements.append(statement)
        # For count queries, return total
        if "count" in str(statement).lower():
            return FakeExecuteResult(total=self._total)
        return FakeExecuteResult(rows=self._rows)


def compile_sql(statement):
    return str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


def create_test_user(user_id=None, equestrian_id=None, username="testuser"):
    """Create a test user entity."""
    return User(
        id=user_id or uuid4(),
        equestrian_id=equestrian_id or uuid4(),
        username=username,
        password="hashed-password",
        first_name="Test",
        last_name="User",
        created_at=datetime.now(timezone.utc),
    )


def create_test_user_row(user_id=None, equestrian_id=None, username="testuser"):
    """Create a test user row dictionary."""
    return {
        "id": user_id or uuid4(),
        "equestrian_id": equestrian_id or uuid4(),
        "username": username,
        "password": "hashed-password",
        "first_name": "Test",
        "last_name": "User",
        "created_at": datetime.now(timezone.utc),
    }


class TestUserRepositoryGetUsersPaginated:
    """Tests for UserRepository.get_users_paginated method."""

    async def test_no_filters(self):
        """Test with no filters applied."""
        # Arrange
        test_user_row = create_test_user_row()
        session = FakeAsyncSession(rows=[test_user_row], total=1)
        repository = UserRepository(session=session)

        # Act
        users, total = await repository.get_users_paginated()

        # Assert
        assert total == 1
        assert len(users) == 1
        assert users[0].id == test_user_row["id"]

    async def test_filter_by_equestrian_ids(self):
        """Test filtering by equestrian_ids."""
        # Arrange
        equestrian_id = uuid4()
        test_user_row = create_test_user_row(equestrian_id=equestrian_id)
        session = FakeAsyncSession(rows=[test_user_row], total=1)
        repository = UserRepository(session=session)

        # Act
        users, total = await repository.get_users_paginated(
            equestrian_ids=[equestrian_id]
        )

        # Assert
        assert total == 1
        assert len(users) == 1
        assert users[0].equestrian_id == equestrian_id

        # Verify SQL contains IN clause (check main query, not count query)
        sql = compile_sql(session.statements[1])
        assert "IN" in sql

    async def test_filter_by_equestrian_service_keys(self):
        """Test filtering by equestrian_service_keys."""
        # Arrange
        test_user_row = create_test_user_row()
        session = FakeAsyncSession(rows=[test_user_row], total=1)
        repository = UserRepository(session=session)

        # Act
        users, total = await repository.get_users_paginated(
            equestrian_service_keys=["service-key-1"]
        )

        # Assert
        assert total == 1
        assert len(users) == 1

        # Verify SQL contains JOIN and IN clause (check main query)
        sql = compile_sql(session.statements[1])
        assert "JOIN" in sql
        assert "IN" in sql

    async def test_filter_by_roles(self):
        """Test filtering by roles."""
        # Arrange
        test_user_row = create_test_user_row()
        session = FakeAsyncSession(rows=[test_user_row], total=1)
        repository = UserRepository(session=session)

        # Act
        users, total = await repository.get_users_paginated(roles=["ADMIN"])

        # Assert
        assert total == 1
        assert len(users) == 1

        # Verify SQL contains subquery (check main query)
        sql = compile_sql(session.statements[1])
        assert "IN" in sql

    async def test_multiple_filters_combined_with_and(self):
        """Test that multiple filters are combined with AND logic."""
        # Arrange
        equestrian_id = uuid4()
        test_user_row = create_test_user_row(equestrian_id=equestrian_id)
        session = FakeAsyncSession(rows=[test_user_row], total=1)
        repository = UserRepository(session=session)

        # Act
        users, total = await repository.get_users_paginated(
            equestrian_ids=[equestrian_id], roles=["ADMIN"]
        )

        # Assert
        assert total == 1
        assert len(users) == 1

        # Verify SQL contains AND (check main query)
        sql = compile_sql(session.statements[1])
        assert "AND" in sql

    async def test_pagination_limit_offset(self):
        """Test pagination with limit and offset."""
        # Arrange
        test_user_row = create_test_user_row()
        session = FakeAsyncSession(rows=[test_user_row], total=10)
        repository = UserRepository(session=session)

        # Act
        users, total = await repository.get_users_paginated(limit=5, offset=10)

        # Assert
        assert total == 10
        assert len(users) == 1

        # Verify SQL contains LIMIT and OFFSET (check main query)
        sql = compile_sql(session.statements[1])
        assert "LIMIT" in sql
        assert "OFFSET" in sql

    async def test_empty_result(self):
        """Test with no matching users."""
        # Arrange
        session = FakeAsyncSession(rows=[], total=0)
        repository = UserRepository(session=session)

        # Act
        users, total = await repository.get_users_paginated()

        # Assert
        assert total == 0
        assert len(users) == 0

    async def test_multiple_equestrian_ids(self):
        """Test filtering with multiple equestrian_ids (OR logic within filter)."""
        # Arrange
        equestrian_id1 = uuid4()
        equestrian_id2 = uuid4()
        test_user_row1 = create_test_user_row(equestrian_id=equestrian_id1)
        test_user_row2 = create_test_user_row(equestrian_id=equestrian_id2)
        session = FakeAsyncSession(rows=[test_user_row1, test_user_row2], total=2)
        repository = UserRepository(session=session)

        # Act
        users, total = await repository.get_users_paginated(
            equestrian_ids=[equestrian_id1, equestrian_id2]
        )

        # Assert
        assert total == 2
        assert len(users) == 2

    async def test_multiple_roles(self):
        """Test filtering with multiple roles (OR logic within filter)."""
        # Arrange
        test_user_row = create_test_user_row()
        session = FakeAsyncSession(rows=[test_user_row], total=1)
        repository = UserRepository(session=session)

        # Act
        users, total = await repository.get_users_paginated(roles=["ADMIN", "USER"])

        # Assert
        assert total == 1
        assert len(users) == 1

    async def test_default_pagination_values(self):
        """Test that default pagination values are used."""
        # Arrange
        test_user_row = create_test_user_row()
        session = FakeAsyncSession(rows=[test_user_row], total=1)
        repository = UserRepository(session=session)

        # Act
        users, total = await repository.get_users_paginated()

        # Assert
        assert total == 1

        # Verify SQL uses default limit (100) and offset (0) (check main query)
        sql = compile_sql(session.statements[1])
        assert "100" in sql
        assert "0" in sql
