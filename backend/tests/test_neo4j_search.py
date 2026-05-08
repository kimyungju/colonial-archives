"""Tests for Neo4jService.get_subgraph behaviour after the round-trip
consolidation in Task B3a."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_get_subgraph_returns_none_for_missing_seed():
    """When the centre entity doesn't exist, get_subgraph must return None."""
    from app.services.neo4j_service import Neo4jService

    svc = Neo4jService()

    fake_session = AsyncMock()
    fake_result = AsyncMock()
    fake_result.single = AsyncMock(return_value=None)
    fake_session.run = AsyncMock(return_value=fake_result)

    fake_driver = MagicMock()
    fake_session_ctx = AsyncMock()
    fake_session_ctx.__aenter__.return_value = fake_session
    fake_session_ctx.__aexit__.return_value = None
    fake_driver.session = MagicMock(return_value=fake_session_ctx)

    with patch.object(Neo4jService, "driver", new_callable=lambda: property(lambda self: fake_driver)):
        result = await svc.get_subgraph("nonexistent_id")
    assert result is None


@pytest.mark.asyncio
async def test_get_subgraph_builds_payload_from_single_record():
    """B3a contract: a populated record produces a GraphPayload with
    centre highlighted, neighbour entries, deduped edges, and edges
    correctly highlighted iff incident to the seed."""
    from unittest.mock import AsyncMock, MagicMock, patch
    from app.services.neo4j_service import Neo4jService

    svc = Neo4jService()

    # Build minimal Neo4j-Node-shaped mocks. Real `neo4j.graph.Node` exposes
    # property dict access via `.get(key)` and items via `.items()`.
    def make_entity(canonical_id, name, categories=None):
        node = MagicMock()
        props = {
            "canonical_id": canonical_id,
            "name": name,
            "main_categories": categories or [],
            "sub_category": None,
            "aliases": [],
            "attributes": "{}",
            "evidence_doc_id": None,
            "evidence_page": None,
            "evidence_text_span": None,
            "evidence_confidence": None,
        }
        # neo4j.graph.Node supports both `.get()` and item access in real life;
        # _record_to_graph_node uses `.get()`.
        node.get = lambda key, default=None: props.get(key, default)
        node.items = lambda: props.items()
        return node, props

    center_node, _ = make_entity("singapore", "Singapore")
    raffles_node, _ = make_entity("raffles", "Raffles")

    def make_rel(start, end, rel_type, element_id):
        rel = MagicMock()
        rel.start_node = start
        rel.end_node = end
        rel.type = "RELATED_TO"
        rel.element_id = element_id
        rel_props = {"rel_type": rel_type, "attributes": None}
        rel.get = lambda key, default=None: rel_props.get(key, default)
        return rel

    rel1 = make_rel(center_node, raffles_node, "FOUNDED", "rel:1")
    # Duplicate by source-type-target key to verify dedup.
    rel1_dup = make_rel(center_node, raffles_node, "FOUNDED", "rel:1-dup")

    fake_record = {
        "center": center_node,
        "neighbors": [raffles_node],
        "rel_lists": [[rel1, rel1_dup]],
    }

    fake_session = AsyncMock()
    fake_result = AsyncMock()
    fake_result.single = AsyncMock(return_value=fake_record)
    fake_session.run = AsyncMock(return_value=fake_result)

    fake_session_ctx = AsyncMock()
    fake_session_ctx.__aenter__.return_value = fake_session
    fake_session_ctx.__aexit__.return_value = None
    fake_driver = MagicMock()
    fake_driver.session = MagicMock(return_value=fake_session_ctx)

    with patch.object(
        Neo4jService, "driver",
        new_callable=lambda: property(lambda self: fake_driver),
    ):
        payload = await svc.get_subgraph("singapore")

    assert payload is not None
    assert payload.center_node == "singapore"
    # Centre + one neighbour
    ids = sorted(n.canonical_id for n in payload.nodes)
    assert ids == ["raffles", "singapore"]
    # Centre is highlighted, neighbour is not
    by_id = {n.canonical_id: n for n in payload.nodes}
    assert by_id["singapore"].highlighted is True
    assert by_id["raffles"].highlighted is False
    # Deduped — only one edge despite two relationship objects with same key
    assert len(payload.edges) == 1
    edge = payload.edges[0]
    assert edge.source == "singapore" and edge.target == "raffles"
    assert edge.type == "FOUNDED"
    # Highlighted because seed is one endpoint
    assert edge.highlighted is True
