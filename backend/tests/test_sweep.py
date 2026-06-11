"""Tests for the relevance-gate threshold sweep logic (pure, offline)."""

import pytest

from evals.sweep import suggest_threshold


class TestSuggestThreshold:
    def test_clean_separation_picks_midpoint_of_gap(self):
        result = suggest_threshold(
            in_domain_max_scores=[0.8, 0.9, 0.85],
            ooc_max_scores=[0.1, 0.2, 0.15],
        )
        # gap is [0.2, 0.8] -> midpoint 0.5
        assert result["threshold"] == pytest.approx(0.5)
        assert result["ooc_rejected_rate"] == 1.0
        assert result["overlapping_ooc"] == 0

    def test_in_domain_floor_is_hard_constraint(self):
        result = suggest_threshold(
            in_domain_max_scores=[0.6, 0.9],
            ooc_max_scores=[0.1, 0.7],
        )
        # 0.7 OOC overlaps in-domain floor 0.6 — cannot be rejected without
        # abstaining on a real in-domain question. Threshold stays below 0.6.
        assert result["threshold"] < 0.6
        assert result["overlapping_ooc"] == 1
        assert result["ooc_rejected_rate"] == 0.5

    def test_no_ooc_scores_gives_conservative_threshold(self):
        result = suggest_threshold(
            in_domain_max_scores=[0.8, 0.9],
            ooc_max_scores=[],
        )
        # nothing to reject; gate midpoint between 0 and the floor
        assert 0.0 < result["threshold"] < 0.8
        assert result["ooc_rejected_rate"] is None

    def test_empty_in_domain_raises(self):
        with pytest.raises(ValueError):
            suggest_threshold(in_domain_max_scores=[], ooc_max_scores=[0.1])

    def test_reports_distributions(self):
        result = suggest_threshold(
            in_domain_max_scores=[0.8, 0.9],
            ooc_max_scores=[0.1],
        )
        assert result["in_domain_min"] == 0.8
        assert result["ooc_max"] == 0.1
