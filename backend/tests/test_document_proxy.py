import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.anyio
async def test_signed_url_rejects_blank_doc_id() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/document/signed_url?doc_id=&page=1")

    assert response.status_code == 400
    assert response.json()["detail"] == "doc_id is required"


@pytest.mark.anyio
async def test_proxy_rejects_blank_doc_id() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/document/proxy/")

    assert response.status_code == 400
    assert response.json()["detail"] == "doc_id is required"
