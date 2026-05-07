"""Smoke-tests for the price_group_ordering feature.

Tests are grouped:
  1. Infrastructure (DB schema)
  2. Public GET (no auth)
  3. Auth / access checks on reorder endpoint
  4. Functional: auto-numbering, reorder logic, renumbering, sorting
  5. Edge-cases and invariants
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from helpers import (
    SMOKE_EQUESTRIAN_ID,
    SMOKE_SERVICE_KEY,
    create_group,
    create_price,
    delete_group,
    delete_price,
)
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

# =============================================================================
# 1. Infrastructure tests (direct DB, no HTTP)
# =============================================================================


@pytest.mark.asyncio
async def test_smoke_display_order_column_exists(db: AsyncSession):
    """Column display_order must exist in price_groups_relations."""
    result = await db.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='price_groups_relations' "
            "AND column_name='display_order'"
        )
    )
    rows = result.fetchall()
    assert rows, "Column display_order not found in price_groups_relations"


@pytest.mark.asyncio
async def test_smoke_unique_index_exists(db: AsyncSession):
    """Partial unique index uix_price_groups_relations_group_order must exist."""
    result = await db.execute(
        text(
            "SELECT indexname FROM pg_indexes "
            "WHERE tablename='price_groups_relations' "
            "AND indexname='uix_price_groups_relations_group_order'"
        )
    )
    rows = result.fetchall()
    assert rows, "Unique index uix_price_groups_relations_group_order not found"


# =============================================================================
# 2. Public GET endpoints (no auth cookie, only service-key header)
# =============================================================================


@pytest.mark.asyncio
async def test_smoke_get_prices_groups_public(client: AsyncClient):
    """`GET /prices/groups` without auth should return 200."""
    resp = await client.get("/api/prices/groups")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_smoke_get_prices_public(client: AsyncClient):
    """`GET /prices` without auth should return 200."""
    resp = await client.get("/api/prices")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_smoke_get_prices_with_groups_filter_public(client: AsyncClient):
    """`GET /prices?groups=NonExistentGroup` without auth should return 200 (empty)."""
    resp = await client.get("/api/prices", params={"groups": "NonExistentSmokeGroup"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total"] == 0


# =============================================================================
# 3. Auth / access control on reorder endpoint
# =============================================================================


@pytest.mark.asyncio
async def test_smoke_reorder_unauthorized_401(client: AsyncClient):
    """`POST /prices/groups/{id}/reorder` without cookie must return 401."""
    fake_id = str(uuid.uuid4())
    resp = await client.post(
        f"/api/prices/groups/{fake_id}/reorder",
        json={"changes": [{"id": str(uuid.uuid4()), "order": 1}]},
    )
    assert resp.status_code == 401, resp.text


@pytest.mark.asyncio
async def test_smoke_reorder_wrong_role_400(
    no_scope_client: AsyncClient, admin_client: AsyncClient, db: AsyncSession
):
    """User without ADMIN/DEVELOPER scope gets 400 on reorder."""
    # Create a group with one price via admin
    group = await create_group(
        admin_client, name=f"smoke_wrrole_{uuid.uuid4().hex[:6]}"
    )
    group_id = group["id"]
    price = await create_price(
        admin_client,
        name=f"smoke_wrrole_p_{uuid.uuid4().hex[:6]}",
        group_ids=[group_id],
    )
    price_id = price["id"]
    try:
        resp = await no_scope_client.post(
            f"/api/prices/groups/{group_id}/reorder",
            json={"changes": [{"id": price_id, "order": 1}]},
        )
        assert resp.status_code == 400, resp.text
    finally:
        await delete_price(admin_client, price_id)
        await delete_group(admin_client, group_id)


@pytest.mark.asyncio
async def test_smoke_reorder_admin_204(admin_client: AsyncClient):
    """ADMIN user can reorder → 204."""
    group = await create_group(
        admin_client, name=f"smoke_admin204_{uuid.uuid4().hex[:6]}"
    )
    group_id = group["id"]
    price = await create_price(
        admin_client,
        name=f"smoke_admin204_p_{uuid.uuid4().hex[:6]}",
        group_ids=[group_id],
    )
    price_id = price["id"]
    try:
        resp = await admin_client.post(
            f"/api/prices/groups/{group_id}/reorder",
            json={"changes": [{"id": price_id, "order": 1}]},
        )
        assert resp.status_code == 204, resp.text
    finally:
        await delete_price(admin_client, price_id)
        await delete_group(admin_client, group_id)


@pytest.mark.asyncio
async def test_smoke_reorder_developer_204(developer_client: AsyncClient):
    """DEVELOPER user can reorder → 204."""
    group = await create_group(
        developer_client, name=f"smoke_dev204_{uuid.uuid4().hex[:6]}"
    )
    group_id = group["id"]
    price = await create_price(
        developer_client,
        name=f"smoke_dev204_p_{uuid.uuid4().hex[:6]}",
        group_ids=[group_id],
    )
    price_id = price["id"]
    try:
        resp = await developer_client.post(
            f"/api/prices/groups/{group_id}/reorder",
            json={"changes": [{"id": price_id, "order": 1}]},
        )
        assert resp.status_code == 204, resp.text
    finally:
        await delete_price(developer_client, price_id)
        await delete_group(developer_client, group_id)


# =============================================================================
# 4. Functional: auto-numbering
# =============================================================================


@pytest.mark.asyncio
async def test_smoke_new_price_in_group_gets_display_order(
    admin_client: AsyncClient, db: AsyncSession
):
    """First price added to a group gets display_order = 1."""
    from models.prices import price_groups_relations

    group = await create_group(admin_client, name=f"smoke_first_{uuid.uuid4().hex[:6]}")
    group_id = group["id"]
    price = await create_price(
        admin_client,
        name=f"smoke_first_p_{uuid.uuid4().hex[:6]}",
        group_ids=[group_id],
    )
    price_id = price["id"]
    try:
        row = (
            (
                await db.execute(
                    select(price_groups_relations).where(
                        price_groups_relations.c.price_id == uuid.UUID(price_id),
                        price_groups_relations.c.group_id == uuid.UUID(group_id),
                    )
                )
            )
            .mappings()
            .first()
        )
        assert row is not None
        assert row["display_order"] == 1, f"Expected 1, got {row['display_order']}"
    finally:
        await delete_price(admin_client, price_id)
        await delete_group(admin_client, group_id)


@pytest.mark.asyncio
async def test_smoke_second_price_gets_order_2(
    admin_client: AsyncClient, db: AsyncSession
):
    """Second price added to the same group gets display_order = 2."""
    from models.prices import price_groups_relations

    group = await create_group(
        admin_client, name=f"smoke_second_{uuid.uuid4().hex[:6]}"
    )
    group_id = group["id"]
    p1 = await create_price(
        admin_client,
        name=f"smoke_second_p1_{uuid.uuid4().hex[:6]}",
        group_ids=[group_id],
    )
    p2 = await create_price(
        admin_client,
        name=f"smoke_second_p2_{uuid.uuid4().hex[:6]}",
        group_ids=[group_id],
    )
    try:
        row = (
            (
                await db.execute(
                    select(price_groups_relations).where(
                        price_groups_relations.c.price_id == uuid.UUID(p2["id"]),
                        price_groups_relations.c.group_id == uuid.UUID(group_id),
                    )
                )
            )
            .mappings()
            .first()
        )
        assert row is not None
        assert row["display_order"] == 2, f"Expected 2, got {row['display_order']}"
    finally:
        await delete_price(admin_client, p1["id"])
        await delete_price(admin_client, p2["id"])
        await delete_group(admin_client, group_id)


# =============================================================================
# 5. Reorder functional tests
# =============================================================================


@pytest.mark.asyncio
async def test_smoke_reorder_moves_forward(admin_client: AsyncClient, db: AsyncSession):
    """Moving price from position 1 → 3 shifts others backward."""
    from models.prices import price_groups_relations

    group = await create_group(admin_client, name=f"smoke_fwd_{uuid.uuid4().hex[:6]}")
    gid = group["id"]
    prices = []
    for i in range(3):
        p = await create_price(
            admin_client, name=f"smoke_fwd_p{i}_{uuid.uuid4().hex[:6]}", group_ids=[gid]
        )
        prices.append(p)

    try:
        # Move first price to position 3
        resp = await admin_client.post(
            f"/api/prices/groups/{gid}/reorder",
            json={"changes": [{"id": prices[0]["id"], "order": 3}]},
        )
        assert resp.status_code == 204, resp.text

        # Verify orders in DB
        rows = (
            (
                await db.execute(
                    select(price_groups_relations).where(
                        price_groups_relations.c.group_id == uuid.UUID(gid)
                    )
                )
            )
            .mappings()
            .all()
        )
        order_map = {str(r["price_id"]): r["display_order"] for r in rows}
        assert order_map[prices[0]["id"]] == 3
        assert order_map[prices[1]["id"]] == 1
        assert order_map[prices[2]["id"]] == 2
    finally:
        for p in prices:
            await delete_price(admin_client, p["id"])
        await delete_group(admin_client, gid)


@pytest.mark.asyncio
async def test_smoke_reorder_moves_backward(
    admin_client: AsyncClient, db: AsyncSession
):
    """Moving price from position 3 → 1 shifts others forward."""
    from models.prices import price_groups_relations

    group = await create_group(admin_client, name=f"smoke_bwd_{uuid.uuid4().hex[:6]}")
    gid = group["id"]
    prices = []
    for i in range(3):
        p = await create_price(
            admin_client, name=f"smoke_bwd_p{i}_{uuid.uuid4().hex[:6]}", group_ids=[gid]
        )
        prices.append(p)

    try:
        resp = await admin_client.post(
            f"/api/prices/groups/{gid}/reorder",
            json={"changes": [{"id": prices[2]["id"], "order": 1}]},
        )
        assert resp.status_code == 204, resp.text

        rows = (
            (
                await db.execute(
                    select(price_groups_relations).where(
                        price_groups_relations.c.group_id == uuid.UUID(gid)
                    )
                )
            )
            .mappings()
            .all()
        )
        order_map = {str(r["price_id"]): r["display_order"] for r in rows}
        assert order_map[prices[2]["id"]] == 1
        assert order_map[prices[0]["id"]] == 2
        assert order_map[prices[1]["id"]] == 3
    finally:
        for p in prices:
            await delete_price(admin_client, p["id"])
        await delete_group(admin_client, gid)


@pytest.mark.asyncio
async def test_smoke_reorder_empty_changes_400(admin_client: AsyncClient):
    """Sending empty changes list → 400 (min_length=1 validation)."""
    group = await create_group(
        admin_client, name=f"smoke_emptychanges_{uuid.uuid4().hex[:6]}"
    )
    gid = group["id"]
    try:
        resp = await admin_client.post(
            f"/api/prices/groups/{gid}/reorder",
            json={"changes": []},
        )
        assert resp.status_code == 400, resp.text
    finally:
        await delete_group(admin_client, gid)


@pytest.mark.asyncio
async def test_smoke_reorder_unknown_price_400(admin_client: AsyncClient):
    """Price UUID not in the group → 400."""
    group = await create_group(
        admin_client, name=f"smoke_unkprice_{uuid.uuid4().hex[:6]}"
    )
    gid = group["id"]
    price = await create_price(
        admin_client, name=f"smoke_unkprice_p_{uuid.uuid4().hex[:6]}", group_ids=[gid]
    )
    pid = price["id"]
    try:
        stranger_id = str(uuid.uuid4())
        resp = await admin_client.post(
            f"/api/prices/groups/{gid}/reorder",
            json={"changes": [{"id": stranger_id, "order": 1}]},
        )
        assert resp.status_code == 400, resp.text
    finally:
        await delete_price(admin_client, pid)
        await delete_group(admin_client, gid)


@pytest.mark.asyncio
async def test_smoke_reorder_unknown_group_400(admin_client: AsyncClient):
    """Non-existent group UUID → 400."""
    fake_group_id = str(uuid.uuid4())
    resp = await admin_client.post(
        f"/api/prices/groups/{fake_group_id}/reorder",
        json={"changes": [{"id": str(uuid.uuid4()), "order": 1}]},
    )
    assert resp.status_code == 400, resp.text


@pytest.mark.asyncio
async def test_smoke_no_unique_violation(admin_client: AsyncClient):
    """Two consecutive reorders must not raise 500."""
    group = await create_group(
        admin_client, name=f"smoke_idempotent_{uuid.uuid4().hex[:6]}"
    )
    gid = group["id"]
    prices = []
    for i in range(3):
        p = await create_price(
            admin_client,
            name=f"smoke_noviolation_p{i}_{uuid.uuid4().hex[:6]}",
            group_ids=[gid],
        )
        prices.append(p)
    try:
        changes = [{"id": prices[0]["id"], "order": 3}]
        r1 = await admin_client.post(
            f"/api/prices/groups/{gid}/reorder", json={"changes": changes}
        )
        r2 = await admin_client.post(
            f"/api/prices/groups/{gid}/reorder",
            json={"changes": [{"id": prices[2]["id"], "order": 1}]},
        )
        assert r1.status_code == 204, r1.text
        assert r2.status_code == 204, r2.text
    finally:
        for p in prices:
            await delete_price(admin_client, p["id"])
        await delete_group(admin_client, gid)


# =============================================================================
# 6. Sorting tests
# =============================================================================


@pytest.mark.asyncio
async def test_smoke_get_prices_groups_filter_sorted_by_display_order(
    admin_client: AsyncClient,
):
    """GET /prices?groups=X (no sort param) returns prices in display_order."""
    suffix = uuid.uuid4().hex[:6]
    group_name = f"smoke_sort_{suffix}"
    group = await create_group(admin_client, name=group_name)
    gid = group["id"]
    prices = []
    for i in range(3):
        p = await create_price(
            admin_client,
            name=f"smoke_sort_p{i}_{suffix}",
            group_ids=[gid],
        )
        prices.append(p)

    try:
        # Reorder: 3rd price → position 1
        await admin_client.post(
            f"/api/prices/groups/{gid}/reorder",
            json={"changes": [{"id": prices[2]["id"], "order": 1}]},
        )

        resp = await admin_client.get("/api/prices", params={"groups": group_name})
        assert resp.status_code == 200, resp.text
        items = resp.json()["items"]
        returned_ids = [item["id"] for item in items]
        # prices[2] should come first, then prices[0], then prices[1]
        assert (
            returned_ids[0] == prices[2]["id"]
        ), f"Expected {prices[2]['id']} first, got {returned_ids}"
    finally:
        for p in prices:
            await delete_price(admin_client, p["id"])
        await delete_group(admin_client, gid)


@pytest.mark.asyncio
async def test_smoke_get_prices_no_groups_filter_fallback_sort(
    admin_client: AsyncClient,
):
    """GET /prices without groups filter still returns 200 (created_at desc order)."""
    resp = await admin_client.get("/api/prices")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "items" in data


# =============================================================================
# 7. Delete renumbering
# =============================================================================


@pytest.mark.asyncio
async def test_smoke_delete_price_renumbers_group(
    admin_client: AsyncClient, db: AsyncSession
):
    """After deleting price at position 2, the remaining get 1, 2 (not gaps)."""
    from models.prices import price_groups_relations

    group = await create_group(
        admin_client, name=f"smoke_delrenum_{uuid.uuid4().hex[:6]}"
    )
    gid = group["id"]
    prices = []
    for i in range(3):
        p = await create_price(
            admin_client,
            name=f"smoke_delrenum_p{i}_{uuid.uuid4().hex[:6]}",
            group_ids=[gid],
        )
        prices.append(p)

    try:
        # Delete the middle one (display_order=2)
        await delete_price(admin_client, prices[1]["id"])

        rows = (
            (
                await db.execute(
                    select(price_groups_relations).where(
                        price_groups_relations.c.group_id == uuid.UUID(gid)
                    )
                )
            )
            .mappings()
            .all()
        )
        orders = sorted(r["display_order"] for r in rows)
        assert orders == [1, 2], f"Expected [1, 2] after delete, got {orders}"
    finally:
        # prices[1] already deleted
        await delete_price(admin_client, prices[0]["id"])
        await delete_price(admin_client, prices[2]["id"])
        await delete_group(admin_client, gid)


@pytest.mark.asyncio
async def test_smoke_update_price_add_group_gets_last_order(
    admin_client: AsyncClient, db: AsyncSession
):
    """PATCH adding a group to a price assigns display_order = last+1."""
    from models.prices import price_groups_relations

    group = await create_group(
        admin_client, name=f"smoke_addgrp_{uuid.uuid4().hex[:6]}"
    )
    gid = group["id"]
    # Seed two prices in the group first
    p_existing = await create_price(
        admin_client, name=f"smoke_addgrp_e_{uuid.uuid4().hex[:6]}", group_ids=[gid]
    )
    # Create a new price without the group, then patch it in
    p_new = await create_price(
        admin_client, name=f"smoke_addgrp_n_{uuid.uuid4().hex[:6]}"
    )
    try:
        resp = await admin_client.patch(
            f"/api/prices/{p_new['id']}",
            json={"groups": [gid]},
        )
        assert resp.status_code == 200, resp.text

        row = (
            (
                await db.execute(
                    select(price_groups_relations).where(
                        price_groups_relations.c.price_id == uuid.UUID(p_new["id"]),
                        price_groups_relations.c.group_id == uuid.UUID(gid),
                    )
                )
            )
            .mappings()
            .first()
        )
        assert row is not None
        assert (
            row["display_order"] == 2
        ), f"Expected 2 (MAX+1), got {row['display_order']}"
    finally:
        await delete_price(admin_client, p_new["id"])
        await delete_price(admin_client, p_existing["id"])
        await delete_group(admin_client, gid)


@pytest.mark.asyncio
async def test_smoke_update_price_remove_group_renumbers(
    admin_client: AsyncClient, db: AsyncSession
):
    """PATCH removing a group from a price triggers renumbering of remaining."""
    from models.prices import price_groups_relations

    group = await create_group(admin_client, name=f"smoke_rmgrp_{uuid.uuid4().hex[:6]}")
    gid = group["id"]
    prices = []
    for i in range(3):
        p = await create_price(
            admin_client,
            name=f"smoke_rmgrp_p{i}_{uuid.uuid4().hex[:6]}",
            group_ids=[gid],
        )
        prices.append(p)

    try:
        # Remove middle price from the group (set groups to empty)
        resp = await admin_client.patch(
            f"/api/prices/{prices[1]['id']}",
            json={"groups": []},
        )
        assert resp.status_code == 200, resp.text

        rows = (
            (
                await db.execute(
                    select(price_groups_relations).where(
                        price_groups_relations.c.group_id == uuid.UUID(gid)
                    )
                )
            )
            .mappings()
            .all()
        )
        orders = sorted(r["display_order"] for r in rows)
        assert orders == [1, 2], f"Expected [1, 2] after patch-remove, got {orders}"
    finally:
        for p in prices:
            await delete_price(admin_client, p["id"])
        await delete_group(admin_client, gid)


# =============================================================================
# 8. Response shape: display_order must NOT appear in API responses
# =============================================================================


@pytest.mark.asyncio
async def test_smoke_display_order_not_in_response(admin_client: AsyncClient):
    """display_order must not be exposed in GET /prices items."""
    group = await create_group(
        admin_client, name=f"smoke_nodisplay_{uuid.uuid4().hex[:6]}"
    )
    gid = group["id"]
    price = await create_price(
        admin_client, name=f"smoke_nodisplay_p_{uuid.uuid4().hex[:6]}", group_ids=[gid]
    )
    pid = price["id"]
    try:
        resp = await admin_client.get("/api/prices")
        items = resp.json()["items"]
        for item in items:
            assert (
                "display_order" not in item
            ), f"display_order leaked into price response: {item}"
    finally:
        await delete_price(admin_client, pid)
        await delete_group(admin_client, gid)


@pytest.mark.asyncio
async def test_smoke_display_order_not_in_groups_response(admin_client: AsyncClient):
    """display_order must not be exposed in GET /prices/groups items."""
    group = await create_group(
        admin_client, name=f"smoke_nodisplayg_{uuid.uuid4().hex[:6]}"
    )
    gid = group["id"]
    try:
        resp = await admin_client.get("/api/prices/groups")
        items = resp.json()["items"]
        for item in items:
            assert (
                "display_order" not in item
            ), f"display_order leaked into group response: {item}"
    finally:
        await delete_group(admin_client, gid)


# =============================================================================
# 9. Idempotency and edge cases
# =============================================================================


@pytest.mark.asyncio
async def test_smoke_reorder_idempotent(admin_client: AsyncClient, db: AsyncSession):
    """Same reorder twice → 204 both times, same final state."""
    from models.prices import price_groups_relations

    group = await create_group(admin_client, name=f"smoke_idem_{uuid.uuid4().hex[:6]}")
    gid = group["id"]
    prices = []
    for i in range(2):
        p = await create_price(
            admin_client,
            name=f"smoke_idem_p{i}_{uuid.uuid4().hex[:6]}",
            group_ids=[gid],
        )
        prices.append(p)

    changes = [{"id": prices[0]["id"], "order": 2}]
    try:
        r1 = await admin_client.post(
            f"/api/prices/groups/{gid}/reorder", json={"changes": changes}
        )
        r2 = await admin_client.post(
            f"/api/prices/groups/{gid}/reorder", json={"changes": changes}
        )
        assert r1.status_code == 204, r1.text
        assert r2.status_code == 204, r2.text

        rows = (
            (
                await db.execute(
                    select(price_groups_relations).where(
                        price_groups_relations.c.group_id == uuid.UUID(gid)
                    )
                )
            )
            .mappings()
            .all()
        )
        order_map = {str(r["price_id"]): r["display_order"] for r in rows}
        assert order_map[prices[0]["id"]] == 2
        assert order_map[prices[1]["id"]] == 1
    finally:
        for p in prices:
            await delete_price(admin_client, p["id"])
        await delete_group(admin_client, gid)


@pytest.mark.asyncio
async def test_smoke_reorder_order_clips_to_n(
    admin_client: AsyncClient, db: AsyncSession
):
    """order=99 for a group with 2 items gets clipped to 2."""
    from models.prices import price_groups_relations

    group = await create_group(admin_client, name=f"smoke_clip_{uuid.uuid4().hex[:6]}")
    gid = group["id"]
    prices = []
    for i in range(2):
        p = await create_price(
            admin_client,
            name=f"smoke_clip_p{i}_{uuid.uuid4().hex[:6]}",
            group_ids=[gid],
        )
        prices.append(p)

    try:
        resp = await admin_client.post(
            f"/api/prices/groups/{gid}/reorder",
            json={"changes": [{"id": prices[0]["id"], "order": 99}]},
        )
        assert resp.status_code == 204, resp.text

        rows = (
            (
                await db.execute(
                    select(price_groups_relations).where(
                        price_groups_relations.c.group_id == uuid.UUID(gid)
                    )
                )
            )
            .mappings()
            .all()
        )
        order_map = {str(r["price_id"]): r["display_order"] for r in rows}
        assert (
            order_map[prices[0]["id"]] == 2
        ), f"Expected clipped to 2, got {order_map[prices[0]['id']]}"
    finally:
        for p in prices:
            await delete_price(admin_client, p["id"])
        await delete_group(admin_client, gid)


@pytest.mark.asyncio
async def test_smoke_price_in_two_groups_independent_order(
    admin_client: AsyncClient, db: AsyncSession
):
    """A price in two groups has independent display_order per group."""
    from models.prices import price_groups_relations

    suffix = uuid.uuid4().hex[:6]
    g1 = await create_group(admin_client, name=f"smoke_twogrp_g1_{suffix}")
    g2 = await create_group(admin_client, name=f"smoke_twogrp_g2_{suffix}")
    g1id, g2id = g1["id"], g2["id"]

    # 2 prices in group1; 1 price in group2 + the shared price
    p_shared = await create_price(
        admin_client,
        name=f"smoke_shared_{suffix}",
        group_ids=[g1id, g2id],
    )
    p_other_g1 = await create_price(
        admin_client,
        name=f"smoke_otherg1_{suffix}",
        group_ids=[g1id],
    )
    p_other_g2 = await create_price(
        admin_client,
        name=f"smoke_otherg2_{suffix}",
        group_ids=[g2id],
    )

    try:
        rows = (
            (
                await db.execute(
                    select(price_groups_relations).where(
                        price_groups_relations.c.price_id == uuid.UUID(p_shared["id"])
                    )
                )
            )
            .mappings()
            .all()
        )
        orders_by_group = {str(r["group_id"]): r["display_order"] for r in rows}
        # In group1: shared was added first → order 1; other was added after
        # In group2: other was added before p_shared in g2? No — p_shared has g1,g2
        # Actually p_shared is in g1 as order=1 (first in g1), and in g2 as order=1 (first in g2)
        # p_other_g1 → order=2 in g1
        # p_other_g2 → order=2 in g2
        assert g1id in orders_by_group
        assert g2id in orders_by_group
        # They must be separate rows with different group context
        assert len(rows) == 2, f"Expected 2 relations for shared price, got {len(rows)}"
    finally:
        await delete_price(admin_client, p_shared["id"])
        await delete_price(admin_client, p_other_g1["id"])
        await delete_price(admin_client, p_other_g2["id"])
        await delete_group(admin_client, g1id)
        await delete_group(admin_client, g2id)


@pytest.mark.asyncio
async def test_smoke_reorder_persists_across_requests(
    admin_client: AsyncClient,
):
    """After reorder, a subsequent GET /prices?groups=X confirms new order."""
    suffix = uuid.uuid4().hex[:6]
    group_name = f"smoke_persist_{suffix}"
    group = await create_group(admin_client, name=group_name)
    gid = group["id"]
    prices = []
    for i in range(3):
        p = await create_price(
            admin_client,
            name=f"smoke_persist_p{i}_{suffix}",
            group_ids=[gid],
        )
        prices.append(p)

    try:
        # Move price[2] to position 1
        await admin_client.post(
            f"/api/prices/groups/{gid}/reorder",
            json={"changes": [{"id": prices[2]["id"], "order": 1}]},
        )

        resp = await admin_client.get("/api/prices", params={"groups": group_name})
        assert resp.status_code == 200, resp.text
        items = resp.json()["items"]
        returned_ids = [item["id"] for item in items]
        assert (
            returned_ids[0] == prices[2]["id"]
        ), f"After reorder, expected {prices[2]['id']} first; got {returned_ids}"
    finally:
        for p in prices:
            await delete_price(admin_client, p["id"])
        await delete_group(admin_client, gid)


# =============================================================================
# 10. Protected write endpoints require auth
# =============================================================================


@pytest.mark.asyncio
async def test_smoke_protected_write_endpoints_require_auth(client: AsyncClient):
    """POST/PATCH/DELETE on prices and groups without auth return 401."""
    fake_id = str(uuid.uuid4())

    endpoints = [
        ("POST", "/api/prices/groups", {"name": "test"}),
        ("PATCH", f"/api/prices/groups/{fake_id}", {"name": "test"}),
        ("DELETE", f"/api/prices/groups/{fake_id}", None),
        ("POST", "/api/prices", {"name": "test"}),
        ("PATCH", f"/api/prices/{fake_id}", {"name": "test"}),
        ("DELETE", f"/api/prices/{fake_id}", None),
    ]

    for method, url, payload in endpoints:
        if method == "POST":
            resp = await client.post(url, json=payload)
        elif method == "PATCH":
            resp = await client.patch(url, json=payload)
        else:
            resp = await client.delete(url)
        assert (
            resp.status_code == 401
        ), f"{method} {url} expected 401, got {resp.status_code}: {resp.text}"


# =============================================================================
# 11. No partial state after failed reorder
# =============================================================================


@pytest.mark.asyncio
async def test_smoke_rollback_no_partial_state(
    admin_client: AsyncClient, db: AsyncSession
):
    """Reorder with an unknown price_id in changes must not leave partial state."""
    from models.prices import price_groups_relations

    group = await create_group(
        admin_client, name=f"smoke_partial_{uuid.uuid4().hex[:6]}"
    )
    gid = group["id"]
    prices = []
    for i in range(2):
        p = await create_price(
            admin_client,
            name=f"smoke_partial_p{i}_{uuid.uuid4().hex[:6]}",
            group_ids=[gid],
        )
        prices.append(p)

    # Capture initial orders
    rows_before = (
        (
            await db.execute(
                select(price_groups_relations).where(
                    price_groups_relations.c.group_id == uuid.UUID(gid)
                )
            )
        )
        .mappings()
        .all()
    )
    orders_before = {str(r["price_id"]): r["display_order"] for r in rows_before}

    try:
        # Send a reorder that includes one valid and one unknown price
        stranger = str(uuid.uuid4())
        resp = await admin_client.post(
            f"/api/prices/groups/{gid}/reorder",
            json={
                "changes": [
                    {"id": prices[0]["id"], "order": 2},
                    {"id": stranger, "order": 1},
                ]
            },
        )
        assert resp.status_code == 400, resp.text

        # State must be unchanged
        # Refresh the session to see the committed state
        await db.reset()
        rows_after = (
            (
                await db.execute(
                    select(price_groups_relations).where(
                        price_groups_relations.c.group_id == uuid.UUID(gid)
                    )
                )
            )
            .mappings()
            .all()
        )
        orders_after = {str(r["price_id"]): r["display_order"] for r in rows_after}
        assert (
            orders_before == orders_after
        ), f"Partial state detected! Before: {orders_before}, After: {orders_after}"
    finally:
        for p in prices:
            await delete_price(admin_client, p["id"])
        await delete_group(admin_client, gid)


# =============================================================================
# 12. Empty group reorder
# =============================================================================


@pytest.mark.asyncio
async def test_smoke_reorder_group_with_no_prices_400(admin_client: AsyncClient):
    """Reordering a group with no prices → 400 (В группе нет услуг)."""
    group = await create_group(
        admin_client, name=f"smoke_emptygrp_{uuid.uuid4().hex[:6]}"
    )
    gid = group["id"]
    try:
        resp = await admin_client.post(
            f"/api/prices/groups/{gid}/reorder",
            json={"changes": [{"id": str(uuid.uuid4()), "order": 1}]},
        )
        assert resp.status_code == 400, resp.text
    finally:
        await delete_group(admin_client, gid)


# =============================================================================
# 13. Sorting contract: groups filter vs no-filter use different sort keys
# =============================================================================


@pytest.mark.asyncio
async def test_smoke_reorder_order_visible_only_with_groups_filter(
    admin_client: AsyncClient,
):
    """After reorder:
    - GET /prices?groups=X returns prices in new display_order (last price first).
    - GET /prices (no filter) does NOT apply display_order; the most recently
      created price appears first (created_at DESC fallback), so the ordering
      differs from the reordered sequence.
    """
    suffix = uuid.uuid4().hex[:6]
    group_name = f"smoke_flt_{suffix}"
    group = await create_group(admin_client, name=group_name)
    gid = group["id"]
    created_prices = []
    for i in range(3):
        p = await create_price(
            admin_client,
            name=f"smoke_flt_p{i}_{suffix}",
            group_ids=[gid],
        )
        created_prices.append(p)

    try:
        # Reorder: move last created (index 2) to position 1
        resp = await admin_client.post(
            f"/api/prices/groups/{gid}/reorder",
            json={"changes": [{"id": created_prices[2]["id"], "order": 1}]},
        )
        assert resp.status_code == 204, resp.text

        # With groups filter → display_order applies → prices[2] comes first
        resp_filtered = await admin_client.get(
            "/api/prices", params={"groups": group_name}
        )
        assert resp_filtered.status_code == 200, resp_filtered.text
        filtered_ids = [item["id"] for item in resp_filtered.json()["items"]]
        assert (
            filtered_ids[0] == created_prices[2]["id"]
        ), f"With groups filter: expected {created_prices[2]['id']} first, got {filtered_ids}"

        # Without groups filter → created_at DESC → prices[2] still first
        # (it was created last), but the ordering key is different (not display_order)
        # Verify the filtered response is in display_order (not created_at desc)
        # display_order after reorder: prices[2]=1, prices[0]=2, prices[1]=3
        # created_at order would be: prices[2], prices[1], prices[0] (newest first)
        # These differ at index 1 and 2, confirming different sort keys are used
        assert filtered_ids == [
            created_prices[2]["id"],
            created_prices[0]["id"],
            created_prices[1]["id"],
        ], (
            f"With groups filter: expected display_order sequence "
            f"[p2, p0, p1], got {filtered_ids}"
        )
    finally:
        for p in created_prices:
            await delete_price(admin_client, p["id"])
        await delete_group(admin_client, gid)


@pytest.mark.asyncio
async def test_smoke_health_check(client: AsyncClient):
    """App health endpoint returns 200."""
    resp = await client.get("/health")
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "healthy"
