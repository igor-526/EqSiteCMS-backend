from sqlalchemy import Column, ForeignKey, String, Table

from utils.basemodel import metadata, timestamp_columns, uuid_pk

users = Table(
    "users",
    metadata,
    uuid_pk(),
    *timestamp_columns(),
    Column("username", String(63), unique=True, nullable=False, index=True),
    Column("password", String(255), nullable=False),
    Column(
        "first_name",
        String(63),
        nullable=True,
        comment="Имя пользователя",
    ),
    Column(
        "last_name",
        String(63),
        nullable=True,
        comment="Фамилия пользователя",
    ),
    Column(
        "middle_name",
        String(63),
        nullable=True,
        comment="Отчество пользователя (необязательно)",
    ),
)

user_scopes = Table(
    "user_scopes",
    metadata,
    uuid_pk(),
    Column(
        "scope_name",
        String(63),
        unique=True,
        nullable=False,
        index=True,
        comment="Название области доступа",
    ),
    Column(
        "scope_description",
        String(255),
        nullable=True,
        comment="Описание области доступа",
    ),
)

user_scopes_relations = Table(
    "user_scopes_relations",
    metadata,
    uuid_pk(),
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column(
        "scope_id", ForeignKey("user_scopes.id", ondelete="CASCADE"), nullable=False
    ),
)
