"""UT-SEOP-03: tenant из actor и передача параметров без смены контекста."""

from datetime import datetime, timezone
from unittest.mock import create_autospec
from uuid import uuid4

import pytest

from clients.seo_service.schemas import BlacklistItemInDto
from core.protocols.seo_service import (
    SeoServiceClientProtocol,
    SeoServiceUnavailableError,
)
from core.schemas.users import UserOutDto
from core.services.seo_proxy import SeoProxyService


@pytest.fixture
def actor():
    return UserOutDto(
        id=uuid4(),
        equestrian_id=uuid4(),
        username="admin",
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def client():
    return create_autospec(SeoServiceClientProtocol, instance=True)


@pytest.mark.parametrize("method", ["list_search_queries", "list_pages"])
@pytest.mark.parametrize(
    "limit,offset,expected_limit,expected_offset",
    [
        (500, -1, 100, 0),
        (0, 1, 1, 1),
        (-100, -10, 1, 0),
        (100, 50, 100, 50),
        (20, 0, 20, 0),
    ],
)
async def test_ut_seop_03_lists(
    actor, client, method, limit, offset, expected_limit, expected_offset
):
    service = SeoProxyService(client)
    result = await getattr(service, method)(
        actor=actor,
        search=" лошадь ",
        ordering="-created_at",
        limit=limit,
        offset=offset,
    )
    downstream = getattr(client, method)
    downstream.assert_awaited_once_with(
        equestrian_id=actor.equestrian_id,
        search=" лошадь ",
        ordering="-created_at",
        limit=expected_limit,
        offset=expected_offset,
        **(
            dict(mode=None, metric=None, date_from=None, date_to=None)
            if method in {"list_pages", "list_search_queries"}
            else {}
        ),
    )
    assert result is downstream.return_value


@pytest.mark.parametrize("method", ["list_search_queries", "list_pages"])
async def test_ut_seop_03_default_lists(actor, client, method):
    await getattr(SeoProxyService(client), method)(actor=actor)
    getattr(client, method).assert_awaited_once_with(
        equestrian_id=actor.equestrian_id,
        search=None,
        ordering=None,
        limit=20,
        offset=0,
        **(
            dict(mode=None, metric=None, date_from=None, date_to=None)
            if method in {"list_pages", "list_search_queries"}
            else {}
        ),
    )


@pytest.mark.parametrize("name", ["blacklisted_query_params", "blacklisted_hashes"])
@pytest.mark.parametrize("action", ["list", "create", "update", "delete"])
async def test_ut_seop_03_blacklists(actor, client, name, action):
    method = f"{action}_{name}"
    kwargs = {}
    if action in ("create", "update"):
        kwargs["data"] = BlacklistItemInDto(value="utm_source")
    if action in ("update", "delete"):
        kwargs["item_id"] = uuid4()
    result = await getattr(SeoProxyService(client), method)(actor=actor, **kwargs)
    downstream = getattr(client, method)
    downstream.assert_awaited_once_with(equestrian_id=actor.equestrian_id, **kwargs)
    assert result is (None if action == "delete" else downstream.return_value)


async def test_ut_seop_03_actor_tenant_changes_per_call(actor, client):
    service = SeoProxyService(client)
    await service.list_pages(actor=actor)
    other = actor.model_copy(update={"equestrian_id": uuid4()})
    await service.list_pages(actor=other)
    assert [
        call.kwargs["equestrian_id"] for call in client.list_pages.await_args_list
    ] == [actor.equestrian_id, other.equestrian_id]


async def test_errors_are_not_wrapped(actor, client):
    client.list_pages.side_effect = SeoServiceUnavailableError()
    with pytest.raises(SeoServiceUnavailableError):
        await SeoProxyService(client).list_pages(actor=actor)


async def test_dependency_wiring(monkeypatch):
    from clients.seo_service.client import SeoServiceClient
    from depends.services import get_seo_proxy_service, get_seo_service_client
    from settings import settings

    monkeypatch.setattr(settings, "seo_service_url", "http://configured.invalid")
    client = await get_seo_service_client()
    assert isinstance(client, SeoServiceClient)
    assert client._base_url == "http://configured.invalid"
    assert isinstance(await get_seo_proxy_service(client), SeoProxyService)


async def test_ut_gw02_search_queries_extended_contract(actor, client):
    await SeoProxyService(client).list_search_queries(
        actor=actor, search="лошадь", ordering="-query", limit=5, offset=10
    )
    client.list_search_queries.assert_awaited_once_with(
        equestrian_id=actor.equestrian_id,
        search="лошадь",
        ordering="-query",
        limit=5,
        offset=10,
        mode=None,
        metric=None,
        date_from=None,
        date_to=None,
    )
    client.list_pages.assert_not_awaited()
