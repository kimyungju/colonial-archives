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


@pytest.mark.parametrize(
    "raw,expected_substrings,disallowed",
    [
        # Tokens are lowercased; both prefix-wildcard and fuzzy variants emitted.
        ("Raffles", ["raffles*", "raffles~1"], ["Raffles*", "AND"]),
        ("opium revenue", ["opium*", "revenue~1"], []),
        # Lucene operator keywords (AND/OR/NOT/TO) must be lowercased to terms,
        # NOT stripped — otherwise a real entity called "AND" is unfindable.
        (
            "AND OR NOT",
            ["and*", "and~1", "or*", "or~1", "not*", "not~1"],
            ["AND", "OR", "NOT"],
        ),
        ("", [], []),
        ("a", [], []),  # below 2-char floor
        # Reserved chars stripped; remaining word tokens kept and lowercased.
        ('Raffles + "Stamford"', ["raffles*", "stamford*"], ['"', "+", "Raffles*"]),
    ],
)
def test_sanitise_fulltext_query(raw, expected_substrings, disallowed):
    from app.services.neo4j_service import Neo4jService
    out = Neo4jService._sanitise_fulltext_query(raw)
    for sub in expected_substrings:
        assert sub in out, f"expected {sub!r} in {out!r}"
    for bad in disallowed:
        assert bad not in out, f"unexpected {bad!r} in {out!r}"


def test_sanitise_returns_empty_when_no_tokens():
    """Sanitiser returns empty string only when no usable tokens remain."""
    from app.services.neo4j_service import Neo4jService
    assert Neo4jService._sanitise_fulltext_query("") == ""
    assert Neo4jService._sanitise_fulltext_query("!!! ??? ***") == ""


@pytest.mark.parametrize(
    "msg,expected",
    [
        # Canonical Neo4j 5.x wording.
        ("There is no such fulltext schema index entity_name_fulltext", True),
        # Hyphenated variant (matches Neo4j docs spelling — punctuation
        # normaliser must turn this into the same matched substring).
        ("There is no such full-text schema index entity_name_fulltext", True),
        # Older / shorter variants.
        ("There is no such fulltext index", True),
        ("There is no such full-text index", True),
        ("Index is currently POPULATING", True),
        ("IndexNotFoundException raised", True),
        # Capitalised exception class name.
        ("Caused by: IndexNotFound: foo", True),
        # Negative — must NOT match.
        ("Connection refused", False),
        ("Some unrelated error", False),
        ("Vector index population in progress", True),  # 'populating' substring
    ],
)
def test_is_missing_index_error_matches_neo4j_messages(msg, expected):
    """The fallback gate must trigger for any wording Neo4j uses to say
    'this fulltext index does not exist or is not yet ready', AND must
    survive punctuation drift (full-text vs fulltext)."""
    from app.services.neo4j_service import Neo4jService
    assert Neo4jService._is_missing_index_error(Exception(msg)) is expected


@pytest.mark.asyncio
async def test_search_entities_does_NOT_run_legacy_when_fulltext_succeeds():
    """Hot-path policy: when full-text succeeds, legacy must NOT run.
    Without this guarantee the plan re-introduces the rejected always-parallel
    behavior that doubles Neo4j load per entity hint."""
    from unittest.mock import AsyncMock, patch
    from app.models.schemas import GraphNode
    from app.services.neo4j_service import Neo4jService

    svc = Neo4jService()

    fulltext_nodes = [
        GraphNode(
            canonical_id="ft_0",
            name="FT Hit 0",
            main_categories=[],
            sub_category=None,
            attributes={},
            highlighted=False,
        )
    ]

    with (
        patch.object(
            Neo4jService, "_run_fulltext_query", new_callable=AsyncMock,
        ) as fulltext,
        patch.object(
            Neo4jService, "_search_entities_legacy", new_callable=AsyncMock,
        ) as legacy,
    ):
        fulltext.return_value = fulltext_nodes
        legacy.return_value = []
        results = await svc.search_entities("singapore", limit=5)
        fulltext.assert_awaited_once()
        legacy.assert_not_awaited()
        assert [n.canonical_id for n in results] == ["ft_0"]


@pytest.mark.asyncio
async def test_search_entities_falls_back_to_legacy_when_fulltext_index_missing():
    """During the deploy window where code is live but the migration
    hasn't run yet, full-text raises a missing-index error. The wrapper
    must classify that error and run legacy as a one-shot fallback,
    logging a warning."""
    from unittest.mock import AsyncMock, patch
    from app.models.schemas import GraphNode
    from app.services.neo4j_service import Neo4jService

    svc = Neo4jService()

    async def missing_index(*_args, **_kwargs):
        raise Exception("There is no such fulltext schema index entity_name_fulltext")

    legacy_nodes = [
        GraphNode(
            canonical_id="singapore",
            name="Singapore",
            main_categories=[],
            sub_category=None,
            attributes={},
            highlighted=False,
        )
    ]

    with (
        patch.object(
            Neo4jService, "_run_fulltext_query", side_effect=missing_index,
        ),
        patch.object(
            Neo4jService, "_search_entities_legacy", new_callable=AsyncMock,
        ) as legacy,
    ):
        legacy.return_value = legacy_nodes
        results = await svc.search_entities("singapore", limit=5)
        legacy.assert_awaited_once()
        assert any(n.canonical_id == "singapore" for n in results)


@pytest.mark.asyncio
async def test_search_entities_propagates_unrecognised_fulltext_error():
    """Any non-missing-index full-text error (driver crash, syntax, etc.)
    must propagate — these are real bugs, NOT recall-fallback opportunities."""
    from unittest.mock import AsyncMock, patch
    from app.services.neo4j_service import Neo4jService

    svc = Neo4jService()

    async def driver_failure(*_args, **_kwargs):
        raise RuntimeError("driver connection lost")

    with (
        patch.object(
            Neo4jService, "_run_fulltext_query", side_effect=driver_failure,
        ),
        patch.object(
            Neo4jService, "_search_entities_legacy", new_callable=AsyncMock,
        ) as legacy,
    ):
        legacy.return_value = []
        with pytest.raises(RuntimeError, match="driver connection lost"):
            await svc.search_entities("singapore", limit=5)
        legacy.assert_not_awaited()


@pytest.mark.asyncio
async def test_search_entities_short_circuits_on_blank_query():
    """Whitespace-only input must not hit the database or the legacy
    fallback — it returns [] immediately."""
    from unittest.mock import AsyncMock, patch
    from app.services.neo4j_service import Neo4jService

    svc = Neo4jService()
    with patch.object(
        Neo4jService, "_search_entities_legacy", new_callable=AsyncMock,
    ) as legacy:
        result = await svc.search_entities("   ", limit=5)
        assert result == []
        legacy.assert_not_awaited()


@pytest.mark.asyncio
async def test_search_entities_falls_back_on_empty_sanitised():
    """If the sanitiser eats every token (e.g. all input is Lucene
    reserved chars), search_entities must call the legacy CONTAINS
    path. Otherwise we drop a real user request and break recall."""
    from unittest.mock import AsyncMock, patch
    from app.services.neo4j_service import Neo4jService

    svc = Neo4jService()

    with patch.object(
        Neo4jService, "_search_entities_legacy", new_callable=AsyncMock,
    ) as legacy:
        legacy.return_value = []
        await svc.search_entities("!!! ??? ***", limit=5)
        legacy.assert_awaited_once()
