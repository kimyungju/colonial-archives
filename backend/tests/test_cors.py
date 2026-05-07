"""Regression test for the CORS spec violation in main.py.

allow_origins=["*"] combined with allow_credentials=True is rejected by
all major browsers. This test enforces the wildcard/credentials invariant.
"""

import pytest


def test_cors_wildcard_does_not_allow_credentials(mock_gcp):
    from starlette.middleware.cors import CORSMiddleware

    from app.main import app

    cors_layer = next(
        (m for m in app.user_middleware if m.cls is CORSMiddleware),
        None,
    )
    assert cors_layer is not None, "CORSMiddleware not installed"

    kwargs = cors_layer.kwargs
    if "*" in kwargs.get("allow_origins", []):
        assert kwargs.get("allow_credentials") is False, (
            "allow_origins=['*'] requires allow_credentials=False per CORS spec"
        )
