"""Shared helpers for smoke tests (importable, no pytest fixtures)."""

from __future__ import annotations

import uuid

from httpx import AsyncClient

SMOKE_EQUESTRIAN_ID = uuid.UUID("ecae3909-bfdb-48a2-a7c5-4f4627fe174e")
SMOKE_SERVICE_KEY = "default-equestrian"


async def create_group(client: AsyncClient, *, name: str) -> dict:
    """Create a price group via the API and return the response JSON."""
    resp = await client.post("/api/prices/groups", json={"name": name})
    assert resp.status_code == 200, f"create_group failed: {resp.text}"
    return resp.json()


async def create_price(
    client: AsyncClient, *, name: str, group_ids: list[str] | None = None
) -> dict:
    """Create a price via the API and return the response JSON."""
    payload: dict = {"name": name}
    if group_ids:
        payload["groups"] = group_ids
    resp = await client.post("/api/prices", json=payload)
    assert resp.status_code == 200, f"create_price failed: {resp.text}"
    return resp.json()


async def delete_group(client: AsyncClient, group_id: str) -> None:
    await client.delete(f"/api/prices/groups/{group_id}")


async def delete_price(client: AsyncClient, price_id: str) -> None:
    await client.delete(f"/api/prices/{price_id}")
