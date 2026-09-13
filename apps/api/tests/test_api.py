"""API endpoint tests using the real FastAPI app."""
from __future__ import annotations


def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["database"]["status"] == "ok"


def test_version(client):
    r = client.get("/api/v1/version")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "DocFetch Security Lab"
    assert "rate_limits" in body


def test_dashboard_empty_state(client):
    r = client.get("/api/v1/dashboard/summary")
    assert r.status_code == 200
    body = r.json()
    # Fresh database: zeros and no activity, never fabricated numbers.
    assert body["documents_total"] == 0
    assert body["open_findings"] == 0
    assert body["recent_activity"] == []


def test_findings_empty(client):
    r = client.get("/api/v1/lab/findings")
    assert r.status_code == 200
    assert r.json() == []


def test_downloads_empty(client):
    r = client.get("/api/v1/downloads")
    assert r.status_code == 200
    assert r.json() == []


def test_lab_targets_are_the_allowlisted_defaults(client):
    r = client.get("/api/v1/lab/targets")
    assert r.status_code == 200
    targets = r.json()
    assert len(targets) == 3
    urls = {t["base_url"] for t in targets}
    assert "http://127.0.0.1:9101" in urls


def test_register_external_target_rejected(client):
    r = client.post(
        "/api/v1/lab/targets",
        json={
            "name": "Scribd",
            "base_url": "https://www.scribd.com",
            "environment_type": "network",
            "allowed_test_profiles": ["auth-enforcement"],
        },
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "TARGET_NOT_ALLOWLISTED"


def test_register_local_target_accepted(client):
    r = client.post(
        "/api/v1/lab/targets",
        json={
            "name": "Local Lab",
            "base_url": "http://127.0.0.1:9444",
            "environment_type": "local",
            "allowed_test_profiles": ["auth-enforcement"],
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["authorized"] is True


def test_register_duplicate_target_name_conflicts(client):
    payload = {
        "name": "Dup Lab",
        "base_url": "http://127.0.0.1:9445",
        "environment_type": "local",
        "allowed_test_profiles": ["auth-enforcement"],
    }
    first = client.post("/api/v1/lab/targets", json=payload)
    assert first.status_code == 200

    second = client.post("/api/v1/lab/targets", json=payload)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "TARGET_NAME_TAKEN"


def test_analyze_rejects_loopback(client):
    r = client.post("/api/v1/analyze", json={"url": "http://127.0.0.1:8080/x.pdf"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "SSRF_BLOCKED_PRIVATE"


def test_analyze_rejects_bad_scheme(client):
    r = client.post("/api/v1/analyze", json={"url": "ftp://example.com/x.pdf"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "INVALID_URL"


def test_upload_roundtrip(client, pdf_bytes):
    r = client.post(
        "/api/v1/uploads",
        files={"file": ("synthetic-test.pdf", pdf_bytes, "application/pdf")},
    )
    assert r.status_code == 200
    doc = r.json()["document"]
    assert doc["status"] == "ready"
    assert doc["page_count"] == 2
    did = doc["id"]

    # Real download
    dl = client.get(f"/api/v1/documents/{did}/download")
    assert dl.status_code == 200
    assert dl.content.startswith(b"%PDF-")

    # Preview
    pv = client.get(f"/api/v1/documents/{did}/preview")
    assert pv.status_code == 200
    assert len(pv.json()["pages"]) == 2

    # Raster page
    img = client.get(f"/api/v1/documents/{did}/pages/1")
    assert img.status_code == 200
    assert img.headers["content-type"] == "image/png"

    # Dashboard now reflects a real upload
    d = client.get("/api/v1/dashboard/summary")
    assert d.json()["documents_total"] == 1
    assert d.json()["uploads_total"] == 1


def test_upload_rejects_fake_pdf(client):
    r = client.post(
        "/api/v1/uploads",
        files={"file": ("fake.pdf", b"It is actually HTML.", "application/pdf")},
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "UNSUPPORTED_FORMAT"


def test_error_contract_has_request_id(client):
    r = client.get("/api/v1/documents/nope")
    body = r.json()["error"]
    assert body["code"] == "DOCUMENT_NOT_FOUND"
    assert body["request_id"] is not None


def test_cors_headers_present(client):
    r = client.get("/api/v1/health", headers={"Origin": "http://localhost:5173"})
    assert r.headers.get("access-control-allow-origin") == "*"