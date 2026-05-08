"""Regression test for the vertexai.init region race in EmbeddingsService.

If something else (LlmService, vector_search) calls vertexai.init with a
different region first, EmbeddingsService.model must still pin its model
to GCP_REGION at construction time.
"""

from unittest.mock import patch, MagicMock

import pytest


@pytest.fixture
def fresh_service():
    """Return a fresh EmbeddingsService with no cached model."""
    from app.services.embeddings import EmbeddingsService
    return EmbeddingsService()


def test_model_property_calls_vertexai_init_with_gcp_region(fresh_service):
    """EmbeddingsService.model must call vertexai.init(location=GCP_REGION)
    BEFORE constructing the model, so prior init calls cannot leak the
    wrong region into TextEmbeddingModel.from_pretrained."""
    with (
        patch("app.services.embeddings.vertexai") as mock_vertexai,
        patch("app.services.embeddings.TextEmbeddingModel") as mock_model_cls,
    ):
        call_order: list[str] = []
        mock_vertexai.init.side_effect = lambda **_kw: call_order.append("init")
        mock_model_cls.from_pretrained.side_effect = lambda *_a, **_kw: (
            call_order.append("from_pretrained") or MagicMock()
        )

        _ = fresh_service.model

        # Order matters: init must run BEFORE from_pretrained, otherwise
        # from_pretrained captures whatever region the global state was
        # left in by an earlier service.
        assert call_order == ["init", "from_pretrained"], (
            f"Expected init before from_pretrained, got {call_order}"
        )

        # And the kwargs to init must point at GCP_REGION (not VERTEX_LLM_REGION).
        from app.config.settings import settings
        mock_vertexai.init.assert_called_once()
        call_kwargs = mock_vertexai.init.call_args.kwargs
        assert call_kwargs.get("location") == settings.GCP_REGION, (
            f"Expected location={settings.GCP_REGION}, "
            f"got {call_kwargs.get('location')}"
        )
        assert call_kwargs.get("project") == settings.GCP_PROJECT_ID
