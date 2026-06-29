from types import SimpleNamespace

import pytest
from google.api_core.exceptions import ResourceExhausted

from app.services.llm import LlmService


class _FlakyModel:
    def __init__(self) -> None:
        self.calls = 0

    def generate_content(self, *_args, **_kwargs):
        self.calls += 1
        if self.calls == 1:
            raise ResourceExhausted("quota")
        return SimpleNamespace(text="Recovered answer [archive:1].")


@pytest.mark.asyncio
async def test_generate_answer_retries_resource_exhausted(monkeypatch):
    monkeypatch.setattr("app.services.llm.asyncio.sleep", _fast_sleep)
    model = _FlakyModel()
    service = LlmService()
    service._model = model

    result = await service.generate_answer(
        "What changed?",
        [{"text": "Archive evidence", "cite_type": "archive"}],
    )

    assert result["answer"] == "Recovered answer [archive:1]."
    assert model.calls == 2


async def _fast_sleep(_seconds):
    return None
