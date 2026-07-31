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


def test_m4_no_vps_storage_surface():
    """The upload endpoint is gone; the Tailscale preview proxy is present."""
    client = TestClient(app)
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/v1/agents/jobs/{job_id}/artifact" not in paths
    assert "/api/v1/render-jobs/{job_id}/preview" in paths
    assert "/api/v1/render-jobs/{job_id}/outputs" in paths


def test_m6_publishing_surface():
    """Publishing endpoints are registered (M6)."""
    client = TestClient(app)
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/v1/render-jobs/{job_id}/publish" in paths
    assert "/api/v1/render-jobs/{job_id}/publish-targets" in paths
    assert "/api/v1/publish-targets/{target_id}/manual" in paths
    assert "/api/v1/publish-targets/{target_id}/retry" in paths
    assert "/api/v1/agents/claim-publish" in paths
    assert "/api/v1/agents/jobs/{job_id}/publish-result" in paths


def test_publish_endpoints_require_auth():
    """Publishing must never be reachable without an admin session.

    The DB dependency is stubbed so this exercises the auth guard only (no
    PostgreSQL needed); an unauthenticated request must be rejected before any
    query runs.
    """
    from vvf_api.deps import get_db

    class _NoDb:
        def query(self, *a, **kw):  # pragma: no cover - must never be reached
            raise AssertionError("auth must reject before touching the DB")

        def get(self, *a, **kw):  # pragma: no cover
            raise AssertionError("auth must reject before touching the DB")

        def close(self):
            pass

    app.dependency_overrides[get_db] = lambda: _NoDb()
    try:
        client = TestClient(app)
        assert client.get("/api/v1/render-jobs/rj_x/publish-targets").status_code == 401
        assert client.post("/api/v1/render-jobs/rj_x/publish", json={}).status_code == 401
        assert (
            client.post(
                "/api/v1/publish-targets/pt_x/manual",
                json={"post_url": "https://example.com/p/1"},
            ).status_code
            == 401
        )
        # The agent protocol uses its own token, not the admin session.
        assert client.post("/api/v1/agents/claim-publish", json={"agent_id": "ag_x"}).status_code == 401
    finally:
        app.dependency_overrides.pop(get_db, None)
