"""Integration: the FastAPI app imports cleanly and the health endpoint works."""

from __future__ import annotations

from fastapi.testclient import TestClient

from vvf_api.main import app


def test_app_imports_and_health():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "vvf-api"


def test_openapi_published():
    client = TestClient(app)
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json()["paths"]
    # Key endpoints are registered.
    assert "/api/v1/research-runs" in paths
    assert "/api/v1/agents/claim-job" in paths
    assert "/api/v1/auth/login" in paths
