"""Graph API router for the Colonial Archives Graph-RAG backend.

Provides endpoints for entity subgraph retrieval and entity search
backed by Neo4j.
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import GraphNode, GraphOverviewPayload, GraphPayload
from app.services.neo4j_service import neo4j_service

router = APIRouter(prefix="/graph", tags=["graph"])

# In-memory cache for overview graph (changes infrequently)
_overview_cache: dict[str, tuple[float, GraphOverviewPayload]] = {}
_CACHE_TTL_SECONDS = 300  # 5 minutes

logger = logging.getLogger(__name__)


async def prewarm_overview_cache() -> None:
    """Populate the overview cache at startup so the first browser request is instant."""
    try:
        payload = await neo4j_service.get_overview_graph()
        _overview_cache["overview"] = (time.time(), payload)
        logger.info("Overview cache pre-warmed: %d nodes, %d edges", len(payload.nodes), len(payload.edges))
    except Exception:
        logger.warning("Overview cache pre-warm failed", exc_info=True)


@router.get("/overview", response_model=GraphOverviewPayload)
async def graph_overview() -> GraphOverviewPayload:
    """Return all entities and relationships for the overview visualization.

    Cached in-memory for 5 minutes since the full graph changes infrequently.
    """
    cache_key = "overview"
    now = time.time()

    if cache_key in _overview_cache:
        cached_at, payload = _overview_cache[cache_key]
        if now - cached_at < _CACHE_TTL_SECONDS:
            return payload

    payload = await neo4j_service.get_overview_graph()
    _overview_cache[cache_key] = (now, payload)
    return payload


@router.get("/search", response_model=list[GraphNode])
async def graph_search(
    q: str,
    limit: int = Query(default=20, ge=1, le=100),
    categories: list[str] | None = Query(default=None),
) -> list[GraphNode]:
    """Search entities by name or alias.

    Returns a list of matching ``GraphNode`` objects ordered by confidence.
    """
    results = await neo4j_service.search_entities(
        q, limit=limit, categories=categories
    )
    return results


@router.get("/{entity_canonical_id}", response_model=GraphPayload)
async def get_entity(
    entity_canonical_id: str,
    categories: list[str] | None = Query(default=None),
) -> GraphPayload:
    """Get the subgraph surrounding an entity.

    Returns a ``GraphPayload`` with nodes, edges, and the center node ID.
    Raises 404 if the entity does not exist.
    """
    payload = await neo4j_service.get_subgraph(
        entity_canonical_id, categories=categories
    )
    if payload is None:
        raise HTTPException(
            status_code=404,
            detail=f"Entity '{entity_canonical_id}' not found",
        )
    return payload
