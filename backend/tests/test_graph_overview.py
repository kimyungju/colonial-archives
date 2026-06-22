"""Tests for the graph overview endpoint and Neo4j service method."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.models.schemas import GraphOverviewPayload, OverviewNode


@pytest.fixture
def mock_neo4j_driver():
    """Create a mock Neo4j async driver."""
    driver = MagicMock()
    session = AsyncMock()
    # driver.session() must return an async context manager (not a coroutine)
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    driver.session.return_value = ctx
    return driver, session


async def aiter_records(records):
    for r in records:
        yield r


@pytest.mark.asyncio
async def test_get_overview_graph_returns_nodes_with_connection_count(
    mock_neo4j_driver,
):
    """Overview should return nodes with connection_count field."""
    driver, session = mock_neo4j_driver

    # Mock node query result
    node_record = MagicMock()
    node_record.__getitem__ = lambda self, key: {
        "canonical_id": "entity_raffles",
        "name": "Stamford Raffles",
        "main_categories": ["General and Establishment"],
        "sub_category": "Colonial Administrator",
        "attributes": "{}",
        "connection_count": 5,
    }[key]
    node_record.get = lambda key, default=None: {
        "canonical_id": "entity_raffles",
        "name": "Stamford Raffles",
        "main_categories": ["General and Establishment"],
        "sub_category": "Colonial Administrator",
        "attributes": "{}",
        "connection_count": 5,
    }.get(key, default)

    # Mock edge query result
    edge_record = MagicMock()
    edge_record.__getitem__ = lambda self, key: {
        "source_id": "entity_raffles",
        "target_id": "entity_singapore",
        "rel_type": "GOVERNED",
    }[key]

    # First call returns nodes, second call returns edges
    node_result = MagicMock()
    node_result.__aiter__ = lambda self: aiter_records([node_record])

    edge_result = MagicMock()
    edge_result.__aiter__ = lambda self: aiter_records([edge_record])

    call_count = 0

    async def mock_run(query, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return node_result
        return edge_result

    session.run = mock_run

    from app.services.neo4j_service import Neo4jService

    service = Neo4jService()
    service._driver = driver

    result = await service.get_overview_graph()

    assert isinstance(result, GraphOverviewPayload)
    assert len(result.nodes) >= 1
    assert result.nodes[0].connection_count == 5
    assert result.nodes[0].name == "Stamford Raffles"


@pytest.mark.asyncio
async def test_graph_overview_endpoint_returns_200(mock_gcp):
    """GET /graph/overview should return 200 with nodes and edges."""
    mock_payload = GraphOverviewPayload(
        nodes=[
            OverviewNode(
                canonical_id="e1",
                name="Test Entity",
                main_categories=["General and Establishment"],
                connection_count=3,
            )
        ],
        edges=[],
    )

    # Clear the in-memory cache before test
    from app.routers.graph import _overview_cache

    _overview_cache.clear()

    from app.main import app

    with patch(
        "app.routers.graph.neo4j_service.get_overview_graph",
        new_callable=AsyncMock,
        return_value=mock_payload,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/graph/overview")

    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    assert "edges" in data
    assert data["nodes"][0]["connection_count"] == 3
    assert data["nodes"][0]["name"] == "Test Entity"


@pytest.mark.asyncio
async def test_graph_overview_returns_stale_cache_while_refreshing(mock_gcp):
    stale_payload = GraphOverviewPayload(
        nodes=[
            OverviewNode(
                canonical_id="stale",
                name="Stale Entity",
                main_categories=["General and Establishment"],
                connection_count=1,
            )
        ],
        edges=[],
    )
    fresh_payload = GraphOverviewPayload(
        nodes=[
            OverviewNode(
                canonical_id="fresh",
                name="Fresh Entity",
                main_categories=["Economic and Financial"],
                connection_count=2,
            )
        ],
        edges=[],
    )

    from app.routers import graph

    graph._overview_cache.clear()
    graph._overview_refresh_task = None
    graph._overview_cache["overview"] = (
        time.time() - graph._CACHE_TTL_SECONDS - 1,
        stale_payload,
    )

    created_coroutines = []

    def fake_create_task(coro):
        created_coroutines.append(coro)
        coro.close()
        task = MagicMock()
        task.done.return_value = False
        return task

    from app.main import app

    with (
        patch(
            "app.routers.graph.neo4j_service.get_overview_graph",
            new_callable=AsyncMock,
            return_value=fresh_payload,
        ) as get_overview_graph,
        patch("app.routers.graph.asyncio.create_task", side_effect=fake_create_task),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/graph/overview")

    graph._overview_refresh_task = None
    graph._overview_cache.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["nodes"][0]["canonical_id"] == "stale"
    assert len(created_coroutines) == 1
    assert get_overview_graph.await_count == 0
