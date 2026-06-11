"""Offline unit tests for eval metric functions (no live services)."""

import pytest

from evals import metrics


class TestAbstention:
    def test_detects_fallback(self):
        assert metrics.is_abstention("I cannot answer this based on the available sources.")

    def test_detects_fallback_case_insensitive_with_noise(self):
        assert metrics.is_abstention("  i cannot answer this based on the available sources.  ")

    def test_real_answer_not_abstention(self):
        assert not metrics.is_abstention("Tin and gambier were traded [archive:1].")

    def test_empty_is_not_abstention(self):
        assert not metrics.is_abstention("")


class TestCitationMarkers:
    def test_extracts_archive_and_web(self):
        markers = metrics.citation_markers("A [archive:1] and B [web:2] and C [archive:3].")
        assert markers == [("archive", 1), ("web", 2), ("archive", 3)]

    def test_has_inline_citation(self):
        assert metrics.has_inline_citation("x [archive:1]")
        assert not metrics.has_inline_citation("no citation here")


class TestRecallAtK:
    def test_full_recall(self):
        assert metrics.recall_at_k(["d1", "d2"], ["d1", "d2", "d3"], 5) == 1.0

    def test_partial_recall(self):
        assert metrics.recall_at_k(["d1", "d9"], ["d1", "d2", "d3"], 5) == 0.5

    def test_respects_k_cutoff(self):
        # d2 is outside top-1
        assert metrics.recall_at_k(["d2"], ["d1", "d2"], 1) == 0.0

    def test_none_when_no_ground_truth(self):
        assert metrics.recall_at_k([], ["d1"], 5) is None


class TestCitationGrounding:
    def test_all_grounded(self):
        markers = [("archive", 1), ("archive", 2)]
        assert metrics.citation_grounding_rate(markers, n_archive=3, n_web=0) == 1.0

    def test_invented_citation_detected(self):
        # [archive:5] but only 2 archive citations returned
        markers = [("archive", 1), ("archive", 5)]
        assert metrics.citation_grounding_rate(markers, n_archive=2, n_web=0) == 0.5

    def test_web_marker_checks_web_count(self):
        markers = [("web", 1)]
        assert metrics.citation_grounding_rate(markers, n_archive=0, n_web=1) == 1.0
        assert metrics.citation_grounding_rate(markers, n_archive=5, n_web=0) == 0.0

    def test_none_when_no_markers(self):
        assert metrics.citation_grounding_rate([], 3, 0) is None


class TestMRR:
    def test_expected_doc_first_is_one(self):
        assert metrics.mrr(["d1"], ["d1", "d2"]) == 1.0

    def test_expected_doc_second_is_half(self):
        assert metrics.mrr(["d2"], ["d1", "d2"]) == 0.5

    def test_earliest_expected_doc_counts(self):
        # d9 at rank 2 beats d1 at rank 4
        assert metrics.mrr(["d1", "d9"], ["x", "d9", "y", "d1"]) == 0.5

    def test_zero_when_no_expected_doc_cited(self):
        assert metrics.mrr(["d1"], ["x", "y"]) == 0.0

    def test_none_when_no_ground_truth(self):
        assert metrics.mrr([], ["d1"]) is None


class TestNDCGAtK:
    def test_perfect_ranking_is_one(self):
        assert metrics.ndcg_at_k(["d1", "d2"], ["d1", "d2", "x"], 5) == 1.0

    def test_relevant_doc_at_rank_two(self):
        # DCG = 1/log2(3), IDCG = 1/log2(2) = 1
        import math
        expected = (1 / math.log2(3))
        assert metrics.ndcg_at_k(["d1"], ["x", "d1"], 5) == pytest.approx(expected)

    def test_zero_when_nothing_relevant_in_top_k(self):
        assert metrics.ndcg_at_k(["d1"], ["x", "y"], 5) == 0.0

    def test_respects_k_cutoff(self):
        # relevant doc at rank 6 is outside k=5
        assert metrics.ndcg_at_k(["d1"], ["a", "b", "c", "d", "e", "d1"], 5) == 0.0

    def test_ideal_capped_by_k(self):
        # 3 expected docs but k=2: ideal DCG uses only 2 slots, so a
        # ranking with the 2 best slots filled scores 1.0
        assert metrics.ndcg_at_k(["d1", "d2", "d3"], ["d1", "d2"], 2) == 1.0

    def test_none_when_no_ground_truth(self):
        assert metrics.ndcg_at_k([], ["d1"], 5) is None


class TestAggregateIncludesRankingMetrics:
    def test_aggregate_reports_mean_mrr_and_ndcg(self):
        from evals.runner import aggregate

        results = [
            {"id": "q1", "category": "economic", "success": True, "error": None,
             "abstained": False, "latency_s": 1.0,
             "recall_at_5": 1.0, "mrr": 1.0, "ndcg_at_5": 1.0},
            {"id": "q2", "category": "economic", "success": True, "error": None,
             "abstained": False, "latency_s": 1.0,
             "recall_at_5": 0.5, "mrr": 0.5, "ndcg_at_5": 0.6},
        ]
        summary = aggregate(results)
        assert summary["mean_mrr"] == 0.75
        assert summary["mean_ndcg_at_5"] == 0.8


class TestKeywordCoverage:
    def test_full_coverage(self):
        assert metrics.expected_keywords_present("Tin and gambier trade", ["tin", "gambier"]) == 1.0

    def test_partial_coverage(self):
        assert metrics.expected_keywords_present("Only tin here", ["tin", "opium"]) == 0.5

    def test_none_when_no_keywords(self):
        assert metrics.expected_keywords_present("anything", []) is None
