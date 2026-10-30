"""Strict PDF text extraction for uploaded proposal documents."""

from __future__ import annotations

from typing import BinaryIO


class PDFDocumentError(ValueError):
    """Raised when a PDF cannot provide usable proposal text."""


def _read_bytes(source: bytes | bytearray | BinaryIO) -> bytes:
    if isinstance(source, (bytes, bytearray)):
        data = bytes(source)
    elif hasattr(source, "read"):
        original_position = None
        try:
            if hasattr(source, "tell"):
                original_position = source.tell()
            if hasattr(source, "seek"):
                source.seek(0)
            data = source.read()
        except Exception as exc:
            raise PDFDocumentError(f"Could not read uploaded PDF: {exc}") from exc
        finally:
            if original_position is not None and hasattr(source, "seek"):
                try:
                    source.seek(original_position)
                except Exception:
                    pass
        if not isinstance(data, (bytes, bytearray)):
            raise PDFDocumentError("Uploaded PDF must be a binary file or bytes")
        data = bytes(data)
    else:
        raise TypeError("PDF input must be bytes or a binary file-like object")
    if not data:
        raise PDFDocumentError("Uploaded PDF is empty")
    return data


def extract_pdf_text(source: bytes | bytearray | BinaryIO) -> str:
    """Extract readable text or fail clearly; image-only/empty PDFs are rejected."""
    pdf_bytes = _read_bytes(source)
    try:
        import pymupdf
    except ImportError as exc:
        raise RuntimeError("PDF extraction requires PyMuPDF; install requirements.txt") from exc
    try:
        document = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        try:
            pages = [page.get_text("text") for page in document]
        finally:
            document.close()
    except Exception as exc:
        raise PDFDocumentError(f"Could not read PDF: {exc}") from exc
    text = "\n\n".join(page.strip() for page in pages if page and page.strip()).strip()
    if not text:
        raise PDFDocumentError("PDF contains no extractable text; empty and image-only PDFs are not accepted")
    return text
