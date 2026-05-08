"""Unit tests for the defensive parsing helpers in scripts.neo4j_migration.

We don't run the migration in tests (no real Neo4j), but we do enforce
that the version-string parser handles the formats AuraDB and standard
Neo4j actually emit in production — a crash here aborts the migration
mid-rollout and blocks Phase B."""

import pytest

from scripts.neo4j_migration import _parse_major_version


@pytest.mark.parametrize(
    "version,expected",
    [
        ("5.26.0", 5),
        ("5.26.0-aura", 5),         # AuraDB suffix
        ("5.26.0 (Community)", 5),   # Edition suffix
        ("4.4.30", 4),
        ("5", 5),
        ("  5.10  ", 5),             # leading whitespace
    ],
)
def test_parse_major_version_accepts_valid_strings(version, expected):
    assert _parse_major_version(version) == expected


@pytest.mark.parametrize("version", ["", "aura", "v5.26.0", "unknown"])
def test_parse_major_version_rejects_unparseable(version):
    with pytest.raises(RuntimeError, match="Could not parse Neo4j version"):
        _parse_major_version(version)
