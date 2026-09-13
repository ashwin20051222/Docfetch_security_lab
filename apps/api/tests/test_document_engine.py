"""Upload / document validation tests. Extension and browser MIME are never
trusted — magic bytes rule."""
from __future__ import annotations

from app.core.errors import InvalidDocumentError
from app.services.document_engine import store_upload, validate_upload_bytes


def test_rejects_non_pdf_magic_bytes(db_session):
    data = b"<html><body>not a pdf</body></html>"
    try:
        validate_upload_bytes(data, "notes.html")
        assert False, "expected rejection"
    except InvalidDocumentError as e:
        assert e.code == "UNSUPPORTED_FORMAT"


def test_rejects_empty_file(db_session):
    try:
        validate_upload_bytes(b"", "empty.pdf")
        assert False
    except InvalidDocumentError:
        pass


def test_rejects_exe_renamed_as_pdf(db_session):
    # %PDF- magic must be present, not just the extension.
    data = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff"
    try:
        validate_upload_bytes(data, "evil.pdf")
        assert False
    except InvalidDocumentError:
        pass


def test_accepts_real_pdf(pdf_bytes, db_session):
    doc = store_upload(db_session, pdf_bytes, "synthetic-test.pdf")
    assert doc.status == "ready"
    assert doc.page_count == 2
    assert len(doc.sha256) == 64
    assert doc.mime_type == "application/pdf"
    assert doc.source == "upload"


def test_rejects_corrupted_pdf(db_session):
    data = b"%PDF-1.7\nthis is not a real cross-reference table at all...."
    try:
        validate_upload_bytes(data, "broken.pdf")
        assert False
    except InvalidDocumentError:
        pass


def test_rejects_encrypted_pdf(db_session, pdf_bytes):
    # Create an encrypted PDF at runtime.
    import fitz  # noqa: PLC0415

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    encrypted = doc.tobytes(encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="lab-user")
    doc.close()
    try:
        validate_upload_bytes(encrypted, "secret.pdf")
        assert False
    except InvalidDocumentError as e:
        assert e.code == "ENCRYPTED_DOCUMENT"