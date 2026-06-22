import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.routers import query as query_router


PDF_BYTES = bytes(range(256)) * 100


@pytest.mark.anyio
async def test_signed_url_rejects_blank_doc_id() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/document/signed_url?doc_id=&page=1")

    assert response.status_code == 400
    assert response.json()["detail"] == "doc_id is required"


class FakeStorageService:
    def get_pdf_url(self, doc_id: str) -> str:
        assert doc_id == "sample"
        return "gs://bucket/sample.pdf"

    def get_pdf_size(self, gcs_url: str) -> int:
        assert gcs_url == "gs://bucket/sample.pdf"
        return len(PDF_BYTES)

    def read_pdf_bytes(self, gcs_url: str) -> bytes:
        assert gcs_url == "gs://bucket/sample.pdf"
        return PDF_BYTES

    def read_pdf_range(self, gcs_url: str, start: int, end: int) -> bytes:
        assert gcs_url == "gs://bucket/sample.pdf"
        return PDF_BYTES[start:end + 1]


@pytest.mark.anyio
async def test_proxy_supports_byte_range_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(query_router, "storage_service", FakeStorageService())

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/document/proxy/sample",
            headers={"Range": "bytes=10-19"},
        )

    assert response.status_code == 206
    assert response.headers["accept-ranges"] == "bytes"
    assert response.headers["content-range"] == f"bytes 10-19/{len(PDF_BYTES)}"
    assert response.headers["content-length"] == "10"
    assert response.content == PDF_BYTES[10:20]


@pytest.mark.anyio
async def test_proxy_rejects_unsatisfiable_byte_ranges(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(query_router, "storage_service", FakeStorageService())

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/document/proxy/sample",
            headers={"Range": f"bytes={len(PDF_BYTES)}-"},
        )

    assert response.status_code == 416
    assert response.headers["content-range"] == f"bytes */{len(PDF_BYTES)}"


@pytest.mark.anyio
async def test_proxy_rejects_blank_doc_id() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/document/proxy/")

    assert response.status_code == 400
    assert response.json()["detail"] == "doc_id is required"
