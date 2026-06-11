"""LLM-as-judge faithfulness scoring for the retrieval eval.

Given a question, the agent's answer, and the citation text spans the
retrieval actually returned, ask Vertex Gemini whether each claim in the
answer is supported by those spans. This measures grounding in retrieved
evidence (RAGAS-style faithfulness), NOT world-knowledge correctness — the
judge is explicitly told to ignore outside knowledge.
"""

import asyncio
import json
import logging
import re

import vertexai
from vertexai.generative_models import GenerationConfig, GenerativeModel

from app.config.settings import settings

logger = logging.getLogger(__name__)

JUDGE_PROMPT = """You are a strict grounding evaluator for a retrieval system.

You are given a QUESTION, an ANSWER produced by the system, and the SOURCE
EXCERPTS that were retrieved from a colonial-archive corpus. Decide how well
the ANSWER is SUPPORTED BY THE SOURCE EXCERPTS ALONE.

Rules:
- Judge ONLY against the excerpts. Ignore whether claims are true in the real
  world. If a claim is not supported by the excerpts, it is unfaithful even if
  it is historically accurate.
- Citation markers like [archive:N] are not evidence by themselves.
- An answer that correctly declines to answer for lack of evidence is faithful.

QUESTION:
{question}

ANSWER:
{answer}

SOURCE EXCERPTS:
{sources}

Respond with ONLY a JSON object:
{{"faithfulness": <float 0.0-1.0>, "unsupported_claims": <int>, "reason": "<one sentence>"}}
where faithfulness is the fraction of the answer's factual claims supported by
the excerpts (1.0 = fully grounded, 0.0 = not grounded at all)."""

_model = None


def _get_model():
    global _model
    if _model is None:
        vertexai.init(project=settings.GCP_PROJECT_ID, location=settings.VERTEX_LLM_REGION)
        _model = GenerativeModel(settings.VERTEX_LLM_MODEL)
    return _model


def _parse(text: str) -> float | None:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        return max(0.0, min(1.0, float(data["faithfulness"])))
    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
        return None


async def judge_faithfulness(question: str, answer: str, source_spans: list[str]) -> float | None:
    """Return a 0.0-1.0 faithfulness score, or None if the judge call fails."""
    sources = "\n\n".join(f"[{i+1}] {s}" for i, s in enumerate(source_spans))
    prompt = JUDGE_PROMPT.format(question=question, answer=answer, sources=sources)
    loop = asyncio.get_event_loop()
    try:
        resp = await loop.run_in_executor(
            None,
            lambda: _get_model().generate_content(
                prompt,
                # Gemini 2.5-flash is a thinking model: it spends output tokens
                # on internal reasoning, so a small cap leaves no room for the
                # actual JSON and resp.text comes back empty. Give it headroom.
                generation_config=GenerationConfig(temperature=0.0, max_output_tokens=1024),
            ),
        )
        return _parse(resp.text or "")
    except Exception:  # noqa: BLE001
        logger.exception("faithfulness judge failed")
        return None
