from io import BytesIO

import pymupdf
import pytest

from rfp_eval.document_reader import PDFDocumentError, extract_pdf_text


def pdf_with_text(text="Proposal text"):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def test_extracts_bytes_and_file_like():
    pdf = pdf_with_text()
    assert "Proposal text" in extract_pdf_text(pdf)
    uploaded = BytesIO(pdf)
    uploaded.seek(4)
    assert "Proposal text" in extract_pdf_text(uploaded)
    assert uploaded.tell() == 4


@pytest.mark.parametrize("source", [b"", b"not a pdf", None])
def test_rejects_empty_and_unreadable_inputs(source):
    if source is None:
        with pytest.raises(TypeError):
            extract_pdf_text(source)
    else:
        with pytest.raises(PDFDocumentError):
            extract_pdf_text(source)


def test_rejects_image_only_pdf():
    doc = pymupdf.open()
    page = doc.new_page()
    pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 16, 16), 0)
    pixmap.clear_with(255)
    page.insert_image(page.rect, pixmap=pixmap)
    image_only = doc.tobytes()
    doc.close()
    with pytest.raises(PDFDocumentError, match="no extractable text"):
        extract_pdf_text(image_only)
