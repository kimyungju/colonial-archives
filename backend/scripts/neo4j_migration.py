"""One-shot, idempotent Neo4j schema migration.

Adds:
  * Uniqueness constraint on Entity.canonical_id (also creates a backing
    index, which speeds up MERGE during ingestion).
  * Full-text index on Entity.name and Entity.aliases (LIST<STRING>),
    used by Neo4jService.search_entities.

Pre-condition:
  * Neo4j 5.0 or later. LIST<STRING> support in full-text indexes is a
    5.x feature. The script aborts loudly on older versions so a
    partially-applied migration cannot reach production.

Verification:
  * After applying both DDL statements, the script polls SHOW INDEXES
    and asserts each required index is ONLINE at 100% populationPercent.
    Any failure here means the deploy of Task B2's code MUST NOT proceed.

Run from the backend/ directory:

    python -m scripts.neo4j_migration

Requires NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD in the environment (or
.env loaded by Pydantic settings).
"""

from __future__ import annotations

import asyncio
import logging
import re
import sys

from neo4j import AsyncGraphDatabase

from app.config.settings import settings

logger = logging.getLogger(__name__)

REQUIRED_INDEXES = ["entity_canonical_id_unique", "entity_name_fulltext"]
# Match the leading integer of any version string. Defensively handles
# AuraDB-style suffixes like "5.26.0-aura", "5.26.0 (Community)", or
# any future variant — we only care about the first number, which is
# the major version.
_MAJOR_VERSION_RE = re.compile(r"^\s*(\d+)")

MIGRATIONS: list[tuple[str, str]] = [
    (
        "entity_canonical_id_unique",
        """
        CREATE CONSTRAINT entity_canonical_id_unique IF NOT EXISTS
        FOR (e:Entity) REQUIRE e.canonical_id IS UNIQUE
        """,
    ),
    (
        "entity_name_fulltext",
        """
        CREATE FULLTEXT INDEX entity_name_fulltext IF NOT EXISTS
        FOR (e:Entity) ON EACH [e.name, e.aliases]
        """,
    ),
]


def _parse_major_version(version: str) -> int:
    """Extract the leading integer from a Neo4j version string.

    Tolerates suffixes such as ``5.26.0``, ``5.26.0-aura``,
    ``5.26.0 (Community)``, or any other semver-with-metadata form.
    Raises RuntimeError when the string contains no leading integer
    rather than crashing the whole migration with ValueError.
    """
    match = _MAJOR_VERSION_RE.match(version)
    if match is None:
        raise RuntimeError(
            f"Could not parse Neo4j version from {version!r}; "
            "expected a string starting with a major-version integer."
        )
    return int(match.group(1))


async def assert_neo4j_5x(session) -> None:
    """Abort if the server is not Neo4j 5.0+. LIST<STRING> support in
    full-text indexes is a 5.x feature; running the migration on 4.x
    would silently index aliases incorrectly."""
    result = await session.run(
        "CALL dbms.components() YIELD versions RETURN versions[0] AS version"
    )
    record = await result.single()
    if record is None:
        raise RuntimeError("dbms.components() returned no rows")
    version = str(record["version"])
    major = _parse_major_version(version)
    if major < 5:
        raise RuntimeError(
            f"Neo4j {version} detected; this migration requires 5.0+ "
            "for LIST<STRING> support in full-text indexes."
        )
    print(f"  Neo4j version OK: {version}", flush=True)


async def assert_indexes_online(session) -> None:
    """Verify each required index is ONLINE at 100% populated. Fails
    loudly so a partially-built index never reaches a deploy that
    depends on it."""
    result = await session.run(
        """
        SHOW INDEXES YIELD name, state, populationPercent
        WHERE name IN $names
        RETURN name, state, populationPercent
        """,
        {"names": REQUIRED_INDEXES},
    )
    rows = [r async for r in result]
    by_name = {r["name"]: r for r in rows}
    for required in REQUIRED_INDEXES:
        row = by_name.get(required)
        if row is None:
            raise RuntimeError(f"Index '{required}' is missing after migration")
        state = row["state"]
        pct = row["populationPercent"]
        if state != "ONLINE" or (pct is not None and pct < 100.0):
            raise RuntimeError(
                f"Index '{required}' not ready: "
                f"state={state}, populationPercent={pct}"
            )
        print(f"  {required}: ONLINE, {pct}% populated", flush=True)


async def run_migrations() -> None:
    driver = AsyncGraphDatabase.driver(
        settings.NEO4J_URI,
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
    )
    try:
        async with driver.session() as session:
            print("Checking Neo4j version ...", flush=True)
            await assert_neo4j_5x(session)

            for name, stmt in MIGRATIONS:
                print(f"Applying: {name} ...", flush=True)
                # Consume the result so the async driver guarantees the
                # schema statement has actually executed server-side
                # before we proceed to db.awaitIndexes / SHOW INDEXES.
                # `await session.run(...)` alone returns once the query
                # is queued, not once it has finished.
                result = await session.run(stmt)
                await result.consume()
                print(f"  OK: {name}", flush=True)

            print("Waiting for indexes to come online (60s timeout) ...", flush=True)
            await (await session.run("CALL db.awaitIndexes(60)")).consume()

            print("Verifying indexes ...", flush=True)
            await assert_indexes_online(session)
            print("Migration complete.", flush=True)
    finally:
        await driver.close()


if __name__ == "__main__":
    try:
        asyncio.run(run_migrations())
    except Exception as exc:
        logger.exception("Migration failed")
        print(f"FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
