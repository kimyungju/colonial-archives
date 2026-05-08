"""Neo4j graph database service for the Colonial Archives Graph-RAG backend.

Manages entity and relationship storage using MERGE operations (never CREATE)
to ensure idempotent re-ingestion.  Provides subgraph traversal and entity
search for the query pipeline and graph API endpoints.
"""

from __future__ import annotations

import json
import logging

from neo4j import AsyncGraphDatabase

from app.config.settings import settings
from app.models.schemas import (
    Evidence,
    GraphEdge,
    GraphNode,
    GraphOverviewPayload,
    GraphPayload,
    OverviewNode,
)

logger = logging.getLogger(__name__)


class Neo4jService:
    """Async Neo4j driver wrapper with MERGE-only write operations."""

    def __init__(self) -> None:
        self._driver = None

    @property
    def driver(self):
        if self._driver is None:
            self._driver = AsyncGraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            )
            logger.info(
                "Neo4jService initialised (uri=%s)", settings.NEO4J_URI
            )
        return self._driver

    async def close(self) -> None:
        """Close the driver connection pool."""
        if self._driver is not None:
            await self._driver.close()
            logger.info("Neo4jService driver closed")

    async def verify_connectivity(self) -> bool:
        """Check that the driver can reach Neo4j."""
        try:
            await self.driver.verify_connectivity()
            return True
        except Exception:
            logger.warning("Neo4j connectivity check failed", exc_info=True)
            return False

    # ------------------------------------------------------------------
    # Write operations (MERGE only)
    # ------------------------------------------------------------------

    async def merge_entity(
        self,
        canonical_id: str,
        name: str,
        main_categories: list[str],
        sub_category: str | None,
        aliases: list[str],
        attributes: dict,
        evidence: Evidence,
    ) -> None:
        """MERGE an entity node.  Updates properties and appends aliases."""
        query = """
        MERGE (e:Entity {canonical_id: $canonical_id})
        SET e.name = $name,
            e.main_categories = $main_categories,
            e.sub_category = $sub_category,
            e.attributes = $attributes_json,
            e.evidence_doc_id = $evidence_doc_id,
            e.evidence_page = $evidence_page,
            e.evidence_text_span = $evidence_text_span,
            e.evidence_chunk_id = $evidence_chunk_id,
            e.evidence_confidence = $evidence_confidence
        WITH e
        // Append new aliases without duplicates
        SET e.aliases = [x IN
            coalesce(e.aliases, []) + $aliases
            WHERE x IS NOT NULL | x
        ]
        WITH e
        SET e.aliases = [x IN e.aliases WHERE x IS NOT NULL | x]
        WITH e, e.aliases AS raw
        UNWIND raw AS a
        WITH e, collect(DISTINCT a) AS unique_aliases
        SET e.aliases = unique_aliases
        """
        params = {
            "canonical_id": canonical_id,
            "name": name,
            "main_categories": main_categories,
            "sub_category": sub_category,
            "aliases": aliases,
            "attributes_json": json.dumps(attributes),
            "evidence_doc_id": evidence.doc_id,
            "evidence_page": evidence.page,
            "evidence_text_span": evidence.text_span,
            "evidence_chunk_id": evidence.chunk_id,
            "evidence_confidence": evidence.confidence,
        }
        async with self.driver.session() as session:
            await session.run(query, params)

        logger.debug("Merged entity %s (%s)", canonical_id, name)

    async def merge_relationship(
        self,
        source_canonical_id: str,
        target_canonical_id: str,
        rel_type: str,
        attributes: dict,
        evidence: Evidence,
    ) -> None:
        """MERGE a relationship between two entity nodes."""
        # Sanitise relationship type for Cypher (must be a valid identifier)
        safe_type = rel_type.upper().replace(" ", "_")
        safe_type = "".join(c for c in safe_type if c.isalnum() or c == "_")
        if not safe_type:
            safe_type = "RELATED_TO"

        # Neo4j does not support parameterised relationship types, so we use
        # APOC-free dynamic approach: MERGE with a generic label and store the
        # semantic type as a property.
        query = """
        MATCH (a:Entity {canonical_id: $source_id})
        MATCH (b:Entity {canonical_id: $target_id})
        MERGE (a)-[r:RELATED_TO {rel_type: $rel_type}]->(b)
        SET r.attributes = $attributes_json,
            r.evidence_doc_id = $evidence_doc_id,
            r.evidence_page = $evidence_page,
            r.evidence_text_span = $evidence_text_span,
            r.evidence_chunk_id = $evidence_chunk_id,
            r.evidence_confidence = $evidence_confidence
        """
        params = {
            "source_id": source_canonical_id,
            "target_id": target_canonical_id,
            "rel_type": safe_type,
            "attributes_json": json.dumps(attributes),
            "evidence_doc_id": evidence.doc_id,
            "evidence_page": evidence.page,
            "evidence_text_span": evidence.text_span,
            "evidence_chunk_id": evidence.chunk_id,
            "evidence_confidence": evidence.confidence,
        }
        async with self.driver.session() as session:
            await session.run(query, params)

        logger.debug(
            "Merged relationship %s -[%s]-> %s",
            source_canonical_id,
            safe_type,
            target_canonical_id,
        )

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    async def get_subgraph(
        self,
        canonical_id: str,
        depth: int | None = None,
        categories: list[str] | None = None,
    ) -> GraphPayload | None:
        """Return the subgraph within *depth* hops of an entity.

        Single-query implementation: centre, neighbours, and edges are
        fetched in one Cypher round-trip. Returns None if the seed entity
        does not exist.

        Match direction is **outbound only** (`-[r]->`), unchanged from
        the pre-plan implementation. The undirected widening (which is
        a real recall bug fix) is handled separately in Task B3b so the
        round-trip optimisation can be deployed and observed on its own.
        Category filtering is applied in Python after the fetch; Task B3b
        will push it into Cypher together with the directionality and
        size-cap changes.
        """
        if depth is None:
            depth = settings.GRAPH_HOP_DEPTH

        cypher = f"""
        MATCH (center:Entity {{canonical_id: $canonical_id}})
        OPTIONAL MATCH (center)-[r:RELATED_TO*1..{depth}]->(neighbor:Entity)
        WITH center,
             collect(DISTINCT neighbor) AS neighbors,
             collect(DISTINCT r) AS rel_lists
        RETURN center, neighbors, rel_lists
        """
        params = {"canonical_id": canonical_id}

        async with self.driver.session() as session:
            result = await session.run(cypher, params)
            record = await result.single()

        if record is None:
            return None

        center_node = record["center"]
        nodes_map: dict[str, GraphNode] = {
            canonical_id: self._record_to_graph_node(center_node, highlighted=True),
        }

        for neighbor in record["neighbors"]:
            if neighbor is None:
                continue
            nid = neighbor.get("canonical_id", "")
            if not nid or nid in nodes_map:
                continue
            node = self._record_to_graph_node(neighbor, highlighted=False)
            if categories and not any(c in node.main_categories for c in categories):
                continue
            nodes_map[nid] = node

        edges: list[GraphEdge] = []
        seen_edges: set[str] = set()

        # rel_lists is list[list[Relationship]]; flatten and dedupe.
        for rel_list in record["rel_lists"] or []:
            if rel_list is None:
                continue
            for rel in rel_list:
                if rel is None:
                    continue
                source_id = rel.start_node.get("canonical_id", "") if rel.start_node else ""
                target_id = rel.end_node.get("canonical_id", "") if rel.end_node else ""
                rel_type = rel.get("rel_type") or rel.type or "RELATED_TO"

                if source_id not in nodes_map or target_id not in nodes_map:
                    continue

                edge_key = f"{source_id}-{rel_type}-{target_id}"
                if edge_key in seen_edges:
                    continue
                seen_edges.add(edge_key)

                attrs: dict = {}
                raw_attrs = rel.get("attributes")
                if raw_attrs:
                    try:
                        attrs = json.loads(raw_attrs)
                    except (json.JSONDecodeError, TypeError):
                        pass

                edges.append(
                    GraphEdge(
                        id=f"edge_{rel.element_id}",
                        source=source_id,
                        target=target_id,
                        type=rel_type,
                        attributes=attrs,
                        highlighted=(
                            source_id == canonical_id or target_id == canonical_id
                        ),
                    )
                )

        return GraphPayload(
            nodes=list(nodes_map.values()),
            edges=edges,
            center_node=canonical_id,
        )

    async def search_entities(
        self,
        query_text: str,
        limit: int = 20,
        categories: list[str] | None = None,
    ) -> list[GraphNode]:
        """Search entities by name or alias.

        Uses a two-step strategy:
        1. Exact CONTAINS substring match (original behaviour).
        2. If no results, fall back to word-split search — each word in the
           query is matched individually, and results are ranked by the number
           of matching words (more matches = higher rank).
        """
        search_term = query_text.lower()

        # --- Step 1: exact CONTAINS (original approach) ---
        exact_cypher = """
        MATCH (e:Entity)
        WHERE toLower(e.name) CONTAINS $search_term
           OR any(alias IN coalesce(e.aliases, [])
                  WHERE toLower(alias) CONTAINS $search_term)
        RETURN e
        ORDER BY e.evidence_confidence DESC
        LIMIT $limit
        """
        exact_params = {"search_term": search_term, "limit": limit}

        async with self.driver.session() as session:
            result = await session.run(exact_cypher, exact_params)
            records = [r async for r in result]

        method = "exact"

        # --- Step 2: word-split fallback ---
        if not records:
            words = [w for w in search_term.split() if len(w) >= 2]
            if words:
                word_cypher = """
                MATCH (e:Entity)
                WHERE any(word IN $words WHERE toLower(e.name) CONTAINS word)
                   OR any(word IN $words WHERE any(alias IN coalesce(e.aliases, [])
                          WHERE toLower(alias) CONTAINS word))
                WITH e,
                     size([word IN $words WHERE toLower(e.name) CONTAINS word]) AS name_matches,
                     size([word IN $words WHERE any(alias IN coalesce(e.aliases, [])
                           WHERE toLower(alias) CONTAINS word)]) AS alias_matches
                WITH e, name_matches + alias_matches AS match_count
                ORDER BY match_count DESC, e.evidence_confidence DESC
                LIMIT $limit
                RETURN e
                """
                word_params = {"words": words, "limit": limit}

                async with self.driver.session() as session:
                    result = await session.run(word_cypher, word_params)
                    records = [r async for r in result]

                method = "word_split"

        nodes: list[GraphNode] = []
        for rec in records:
            node = self._record_to_graph_node(rec["e"], highlighted=False)
            if categories and not any(c in node.main_categories for c in categories):
                continue
            nodes.append(node)

        logger.debug(
            "Entity search for '%s': %d results (method=%s)",
            query_text,
            len(nodes),
            method,
        )
        return nodes

    async def get_all_entity_names(self) -> list[dict]:
        """Return all entity canonical_ids, names, and aliases for normalization."""
        cypher = """
        MATCH (e:Entity)
        RETURN e.canonical_id AS canonical_id,
               e.name AS name,
               coalesce(e.aliases, []) AS aliases
        """
        async with self.driver.session() as session:
            result = await session.run(cypher)
            records = [r async for r in result]

        return [
            {
                "canonical_id": rec["canonical_id"],
                "name": rec["name"],
                "aliases": list(rec["aliases"]),
            }
            for rec in records
        ]

    async def get_entity_ids_with_prefix(self, prefix: str) -> list[str]:
        """Return all canonical_ids starting with *prefix*."""
        cypher = """
        MATCH (e:Entity)
        WHERE e.canonical_id STARTS WITH $prefix
        RETURN e.canonical_id AS canonical_id
        """
        async with self.driver.session() as session:
            result = await session.run(cypher, {"prefix": prefix})
            records = [r async for r in result]

        return [rec["canonical_id"] for rec in records]

    async def get_overview_graph(self) -> GraphOverviewPayload:
        """Return all entities and relationships for the overview visualization.

        Each node includes a connection_count (number of relationships) so the
        frontend can size nodes proportionally.
        """
        nodes: list[OverviewNode] = []
        edges: list[GraphEdge] = []

        async with self.driver.session() as session:
            # Fetch all entities with their connection counts
            node_result = await session.run(
                """
                MATCH (e:Entity)
                OPTIONAL MATCH (e)-[r:RELATED_TO]-()
                WITH e, count(r) AS connection_count
                RETURN e.canonical_id AS canonical_id,
                       e.name AS name,
                       coalesce(e.main_categories, []) AS main_categories,
                       e.sub_category AS sub_category,
                       connection_count,
                       e.evidence_doc_id AS evidence_doc_id,
                       e.evidence_page AS evidence_page
                ORDER BY connection_count DESC
                """
            )
            async for record in node_result:
                nodes.append(
                    OverviewNode(
                        canonical_id=record["canonical_id"],
                        name=record["name"],
                        main_categories=list(record["main_categories"]),
                        sub_category=record.get("sub_category"),
                        connection_count=record["connection_count"],
                        evidence_doc_id=record.get("evidence_doc_id"),
                        evidence_page=record.get("evidence_page"),
                    )
                )

            # Fetch all relationships
            edge_result = await session.run(
                """
                MATCH (a:Entity)-[r:RELATED_TO]->(b:Entity)
                RETURN a.canonical_id AS source_id,
                       b.canonical_id AS target_id,
                       r.rel_type AS rel_type
                """
            )
            edge_idx = 0
            async for record in edge_result:
                edges.append(
                    GraphEdge(
                        id=f"overview_edge_{edge_idx}",
                        source=record["source_id"],
                        target=record["target_id"],
                        type=record["rel_type"] or "RELATED_TO",
                        attributes={},
                        highlighted=False,
                    )
                )
                edge_idx += 1

        logger.info(
            "Overview graph: %d nodes, %d edges", len(nodes), len(edges)
        )
        return GraphOverviewPayload(nodes=nodes, edges=edges)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _record_to_graph_node(
        node_record,
        highlighted: bool = False,
    ) -> GraphNode:
        """Convert a Neo4j node record to a GraphNode Pydantic model."""
        attrs = {}
        raw_attrs = node_record.get("attributes")
        if raw_attrs:
            try:
                attrs = json.loads(raw_attrs)
            except (json.JSONDecodeError, TypeError):
                pass

        return GraphNode(
            canonical_id=node_record.get("canonical_id", ""),
            name=node_record.get("name", ""),
            main_categories=list(node_record.get("main_categories", [])),
            sub_category=node_record.get("sub_category"),
            attributes=attrs,
            highlighted=highlighted,
            evidence_doc_id=node_record.get("evidence_doc_id"),
            evidence_page=node_record.get("evidence_page"),
            evidence_text_span=node_record.get("evidence_text_span"),
            evidence_confidence=node_record.get("evidence_confidence"),
        )


# Module-level singleton
neo4j_service = Neo4jService()
