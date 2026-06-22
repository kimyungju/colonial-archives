"""Query router -- Q&A, document signed-URL, and PDF proxy endpoints."""

import asyncio
import json
import logging
from urllib.parse import quote

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import Response

from app.config.settings import settings
from app.models.schemas import QueryRequest, QueryResponse, SignedUrlResponse
from app.services.hybrid_retrieval import hybrid_retrieval_service
from app.services.storage import storage_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["query"])


def require_doc_id(doc_id: str) -> str:
    normalized = doc_id.strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="doc_id is required")
    return normalized


def range_not_satisfiable(total_size: int) -> HTTPException:
    return HTTPException(
        status_code=416,
        detail="Requested range is not satisfiable",
        headers={"Content-Range": f"bytes */{total_size}"},
    )


def parse_byte_range(range_header: str, total_size: int) -> tuple[int, int]:
    if not range_header.startswith("bytes=") or "," in range_header:
        raise range_not_satisfiable(total_size)

    start_text, separator, end_text = range_header[len("bytes="):].partition("-")
    if separator != "-":
        raise range_not_satisfiable(total_size)

    try:
        if start_text == "":
            suffix_length = int(end_text)
            if suffix_length <= 0:
                raise ValueError
            start = max(total_size - suffix_length, 0)
            end = total_size - 1
        else:
            start = int(start_text)
            end = int(end_text) if end_text else total_size - 1
    except ValueError as exc:
        raise range_not_satisfiable(total_size) from exc

    if start < 0 or start >= total_size or end < start:
        raise range_not_satisfiable(total_size)

    return start, min(end, total_size - 1)


@router.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest) -> QueryResponse:
    """Run a hybrid retrieval query and return the answer with citations."""
    return await hybrid_retrieval_service.query(
        question=request.question,
        filter_categories=request.filter_categories,
    )


@router.get("/document/signed_url", response_model=SignedUrlResponse)
async def document_signed_url(
    doc_id: str, page: int = 1,
) -> SignedUrlResponse:
    """Generate a temporary signed URL for a document PDF.

    If signed URL generation fails (e.g. running with user ADC credentials),
    falls back to a proxy URL that streams the PDF through the backend.
    """
    doc_id = require_doc_id(doc_id)
    pdf_url = storage_service.get_pdf_url(doc_id)

    try:
        signed_url = await asyncio.get_event_loop().run_in_executor(
            None, storage_service.generate_signed_url, pdf_url,
        )
    except Exception as exc:
        logger.warning("Signed URL generation raised: %s", exc)
        signed_url = None

    if signed_url is not None:
        return SignedUrlResponse(
            url=signed_url,
            expires_in=settings.SIGNED_URL_EXPIRY_MINUTES * 60,
        )

    # Fallback: return a proxy URL served by this backend
    encoded_doc_id = quote(doc_id, safe="")
    proxy_url = f"/document/proxy/{encoded_doc_id}"
    logger.info("Using proxy URL fallback for doc_id=%s", doc_id)
    return SignedUrlResponse(url=proxy_url, expires_in=3600)


@router.get("/document/{doc_id:path}/pages/{page}/text")
async def document_page_text(doc_id: str, page: int) -> dict:
    """Return raw OCR text for a specific page of a document.

    Reads the OCR JSON from GCS (``ocr/{doc_id}_ocr.json``) and returns
    the text and confidence for the requested page number.
    """
    blob_path = f"ocr/{doc_id}_ocr.json"
    try:
        blob = storage_service._bucket.blob(blob_path)
        loop = asyncio.get_event_loop()
        raw = await loop.run_in_executor(None, blob.download_as_text)
        pages = json.loads(raw)
    except Exception:
        logger.warning("OCR data not found for %s", doc_id)
        raise HTTPException(status_code=404, detail=f"OCR data not found for '{doc_id}'")

    # Find the requested page (1-indexed)
    for p in pages:
        if p["page_number"] == page:
            return {
                "doc_id": doc_id,
                "page": page,
                "text": p["text"],
                "confidence": p.get("confidence", 0.0),
                "total_pages": len(pages),
            }

    raise HTTPException(
        status_code=404,
        detail=f"Page {page} not found in '{doc_id}' (total pages: {len(pages)})",
    )


@router.get("/document/{doc_id:path}/text")
async def document_full_text(
    doc_id: str,
    page_start: int | None = None,
    page_end: int | None = None,
):
    """Retrieve OCR text for all pages or a page range of a document.

    - No query params: returns all pages
    - page_start + page_end: returns pages in that range (inclusive)
    - page_start only: returns from that page to the end
    """
    blob_path = f"ocr/{doc_id}_ocr.json"
    try:
        blob = storage_service._bucket.blob(blob_path)
        loop = asyncio.get_event_loop()
        raw = await loop.run_in_executor(None, blob.download_as_text)
        all_pages = json.loads(raw)
    except Exception:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")

    # Filter by page range if specified
    if page_start is not None:
        end = page_end if page_end is not None else max(p["page_number"] for p in all_pages)
        pages = [p for p in all_pages if page_start <= p["page_number"] <= end]
        pages.sort(key=lambda p: p["page_number"])
    else:
        pages = sorted(all_pages, key=lambda p: p["page_number"])

    return {
        "doc_id": doc_id,
        "total_pages": len(all_pages),
        "pages": pages,
    }


@router.head("/document/proxy/{doc_id:path}")
async def document_proxy_head(doc_id: str) -> Response:
    doc_id = require_doc_id(doc_id)
    pdf_url = storage_service.get_pdf_url(doc_id)

    try:
        pdf_size = await asyncio.get_event_loop().run_in_executor(
            None, storage_service.get_pdf_size, pdf_url,
        )
    except Exception as exc:
        logger.error("Failed to read PDF metadata for doc_id=%s: %s", doc_id, exc)
        raise HTTPException(
            status_code=404,
            detail=f"Document '{doc_id}' not found in storage.",
        ) from exc

    return Response(
        content=b"",
        media_type="application/pdf",
        headers={
            "Accept-Ranges": "bytes",
            "Content-Disposition": f'inline; filename="{doc_id}.pdf"',
            "Content-Length": str(pdf_size),
            "Cache-Control": "private, max-age=3600",
        },
    )


@router.get("/document/proxy/{doc_id:path}")
async def document_proxy(
    doc_id: str,
    range_header: str | None = Header(default=None, alias="Range"),
) -> Response:
    """Stream a PDF from Cloud Storage through the backend.

    This is a fallback for when signed URL generation fails (e.g. local dev
    with user ADC credentials that cannot sign blobs).
    """
    doc_id = require_doc_id(doc_id)
    pdf_url = storage_service.get_pdf_url(doc_id)

    try:
        if range_header:
            pdf_size = await asyncio.get_event_loop().run_in_executor(
                None, storage_service.get_pdf_size, pdf_url,
            )
            start, end = parse_byte_range(range_header, pdf_size)
            pdf_bytes = await asyncio.get_event_loop().run_in_executor(
                None, storage_service.read_pdf_range, pdf_url, start, end,
            )
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                status_code=206,
                headers={
                    "Accept-Ranges": "bytes",
                    "Content-Range": f"bytes {start}-{end}/{pdf_size}",
                    "Content-Length": str(len(pdf_bytes)),
                    "Content-Disposition": f'inline; filename="{doc_id}.pdf"',
                    "Cache-Control": "private, max-age=3600",
                },
            )

        pdf_bytes = await asyncio.get_event_loop().run_in_executor(
            None, storage_service.read_pdf_bytes, pdf_url,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to proxy PDF for doc_id=%s: %s", doc_id, exc)
        raise HTTPException(
            status_code=404,
            detail=f"Document '{doc_id}' not found in storage.",
        ) from exc

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Accept-Ranges": "bytes",
            "Content-Disposition": f'inline; filename="{doc_id}.pdf"',
            "Cache-Control": "private, max-age=3600",
        },
    )
