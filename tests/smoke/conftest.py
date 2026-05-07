"""Smoke-test fixtures for price_group_ordering feature.

Uses a real PostgreSQL database (same as the app uses when running locally).
Each test that modifies data cleans up after itself via explicit deletes.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, insert, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# ──────────────────────────────────────────────────────────────────────────────
# Database URL (mirrors the Docker-Compose dev container)
# ──────────────────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv(
    "SMOKE_DATABASE_URL",
    "postgresql+asyncpg://eqsitecms:eqsitecms@localhost:5433/eqsitecms",
)

# Fixed equestrian for all smoke tests (already seeded in dev DB)
SMOKE_EQUESTRIAN_ID = uuid.UUID("ecae3909-bfdb-48a2-a7c5-4f4627fe174e")
SMOKE_SERVICE_KEY = "default-equestrian"


# ──────────────────────────────────────────────────────────────────────────────
# Session-scoped engine & session factory
# ──────────────────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture(scope="session")
def event_loop():
    """Provide a shared event loop for the entire session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def engine():
    from sqlalchemy.pool import NullPool

    eng = create_async_engine(DATABASE_URL, echo=False, poolclass=NullPool)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture(scope="session")
async def session_factory(engine):
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    return factory


# ──────────────────────────────────────────────────────────────────────────────
# Per-test session (no auto-rollback — tests manage their own cleanup)
# ──────────────────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def db(session_factory) -> AsyncGenerator[AsyncSession, None]:
    """Return a committed session for direct DB inspection/setup.

    Tests that INSERT data must DELETE it themselves in the test body or a
    finally-block.  We deliberately do NOT rollback here so that the ASGI
    client (which runs in the same event loop but a different session) can
    see the data.
    """
    async with session_factory() as session:
        yield session


# ──────────────────────────────────────────────────────────────────────────────
# ASGI client factory helper
# ──────────────────────────────────────────────────────────────────────────────


def _make_app_transport():
    """Return an ASGITransport backed by the real FastAPI app."""
    from depends.utils import get_session
    from main import app

    async def override_get_session():
        from sqlalchemy.pool import NullPool

        eng = create_async_engine(DATABASE_URL, echo=False, poolclass=NullPool)
        factory = async_sessionmaker(eng, expire_on_commit=False, autoflush=False)
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
        await eng.dispose()

    app.dependency_overrides[get_session] = override_get_session
    return ASGITransport(app=app)


# ──────────────────────────────────────────────────────────────────────────────
# Base unauthenticated client
# ──────────────────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def client(session_factory) -> AsyncGenerator[AsyncClient, None]:
    """AsyncClient backed by the real FastAPI app with a real DB session."""
    from depends.utils import get_session
    from main import app

    async def override_get_session():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    app.dependency_overrides[get_session] = override_get_session

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Equestrian-Service-Key": SMOKE_SERVICE_KEY},
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ──────────────────────────────────────────────────────────────────────────────
# Auth helper: create a test user with a known scope and return a JWT cookie
# ──────────────────────────────────────────────────────────────────────────────


async def _create_test_user_with_scope(
    db: AsyncSession,
    *,
    scope_name: str,
    equestrian_id: uuid.UUID,
) -> tuple[uuid.UUID, str, str]:
    """
    Insert a user + scope relation into the DB.

    Returns (user_id, username, raw_password).
    The caller is responsible for deleting the user row afterwards.
    """
    from models.users import user_scopes, user_scopes_relations, users
    from utils.security import Security

    sec = Security()
    username = f"smoke_{scope_name.lower()}_{uuid.uuid4().hex[:8]}"
    raw_password = "SmokePass!123"
    hashed = sec.hash_password(raw_password)
    user_id = uuid.uuid4()

    await db.execute(
        insert(users).values(
            id=user_id,
            equestrian_id=equestrian_id,
            username=username,
            password=hashed,
        )
    )

    # Find the scope_id
    scope_row = (
        (
            await db.execute(
                select(user_scopes).where(user_scopes.c.scope_name == scope_name)
            )
        )
        .mappings()
        .first()
    )
    assert scope_row is not None, f"Scope {scope_name!r} not found in user_scopes"
    scope_id = scope_row["id"]

    relation_id = uuid.uuid4()
    await db.execute(
        insert(user_scopes_relations).values(
            id=relation_id, user_id=user_id, scope_id=scope_id
        )
    )
    await db.commit()
    return user_id, username, raw_password


async def _delete_test_user(db: AsyncSession, user_id: uuid.UUID) -> None:
    from models.users import users

    await db.execute(delete(users).where(users.c.id == user_id))
    await db.commit()


async def _get_token_cookie(client: AsyncClient, username: str, password: str) -> str:
    """Login and return the value of the access_token cookie."""
    resp = await client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    cookie = resp.cookies.get("access_token")
    assert cookie, "No access_token cookie after login"
    return cookie


# ──────────────────────────────────────────────────────────────────────────────
# Authenticated client factories — each creates its OWN AsyncClient instance
# so that multiple auth fixtures can coexist in the same test without sharing
# cookie state.
# ──────────────────────────────────────────────────────────────────────────────


async def _make_authed_client(
    session_factory,
    db: AsyncSession,
    *,
    scope_name: str | None,
) -> AsyncGenerator[AsyncClient, None]:
    """
    Internal generator: create a fresh AsyncClient, optionally authenticate it
    with `scope_name` (None = no scope / plain user), and clean up afterwards.
    """
    from depends.utils import get_session
    from main import app

    async def override_get_session():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    # We must clear and re-set overrides since `client` fixture also manages
    # them; using a fresh engine+factory per fixture would be safer but heavier.
    # Here we reuse the same override (idempotent).
    app.dependency_overrides[get_session] = override_get_session

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-Equestrian-Service-Key": SMOKE_SERVICE_KEY},
    ) as ac:
        # Create user and optionally assign scope
        if scope_name is not None:
            user_id, username, password = await _create_test_user_with_scope(
                db, scope_name=scope_name, equestrian_id=SMOKE_EQUESTRIAN_ID
            )
        else:
            from models.users import users
            from utils.security import Security

            sec = Security()
            username = f"smoke_noscope_{uuid.uuid4().hex[:8]}"
            password = "SmokePass!123"
            hashed = sec.hash_password(password)
            user_id = uuid.uuid4()
            await db.execute(
                insert(users).values(
                    id=user_id,
                    equestrian_id=SMOKE_EQUESTRIAN_ID,
                    username=username,
                    password=hashed,
                )
            )
            await db.commit()

        token = await _get_token_cookie(ac, username, password)
        ac.cookies.set("access_token", token)
        yield ac

    await _delete_test_user(db, user_id)


@pytest_asyncio.fixture
async def admin_client(session_factory, db: AsyncSession):
    """Independent AsyncClient pre-authenticated with ADMIN scope."""
    async for ac in _make_authed_client(session_factory, db, scope_name="ADMIN"):
        yield ac


@pytest_asyncio.fixture
async def developer_client(session_factory, db: AsyncSession):
    """Independent AsyncClient pre-authenticated with DEVELOPER scope."""
    async for ac in _make_authed_client(session_factory, db, scope_name="DEVELOPER"):
        yield ac


@pytest_asyncio.fixture
async def no_scope_client(session_factory, db: AsyncSession):
    """Independent AsyncClient authenticated with NO scope (plain user)."""
    async for ac in _make_authed_client(session_factory, db, scope_name=None):
        yield ac
