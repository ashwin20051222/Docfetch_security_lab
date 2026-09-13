"""Shared pytest fixtures. The PDF fixture is generated at test time (not a
production-data seed) and is clearly marked as a test fixture in metadata."""
from __future__ import annotations

import importlib
import os
import sys

import pytest

# Ensure the app package is importable regardless of CWD.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Isolate the database per test run.
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_data/test.db")
os.environ.setdefault("DATA_DIR", "./test_data")


@pytest.fixture(scope="session")
def pdf_bytes() -> bytes:
    """A real, valid, 2-page PDF generated at runtime. TEST FIXTURE."""
    import fitz  # noqa: PLC0415

    doc = fitz.open()
    for _ in range(2):
        page = doc.new_page()
        page.insert_text((72, 72), "DOCFETCH TEST FIXTURE — synthetic content for automated tests")
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture(scope="function")
def client():
    from fastapi.testclient import TestClient  # noqa: PLC0415

    from app.main import app, on_startup  # noqa: PLC0415

    on_startup()
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="function")
def db_session():
    from app.database import SessionLocal, engine  # noqa: PLC0415
    from app import models  # noqa: PLC0415, F401
    from app.database import Base  # noqa: PLC0415

    # Ensure tables + sqlite parent dir exist even when a Lab test runs alone.
    from pathlib import Path  # noqa: PLC0415
    import os  # noqa: PLC0415

    db_url = os.environ.get("DATABASE_URL", "sqlite:///./test_data/test.db")
    if db_url.startswith("sqlite:///") and db_url != "sqlite:///:memory:":
        Path(db_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)

    session = SessionLocal()
    yield session
    session.close()