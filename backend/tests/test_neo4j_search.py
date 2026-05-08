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
