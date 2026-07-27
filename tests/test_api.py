"""End-to-end CRUD flow through FastAPI, against the memory backend."""

import pytest
from fastapi.testclient import TestClient

from creative_director.api.app import create_app
from creative_director.config import Settings
from creative_director.repositories.factory import build_memory_repositories

API_KEY = "test-key"
AUTH = {"X-API-Key": API_KEY}


@pytest.fixture
def client():
    settings = Settings(_env_file=None, app_api_key=API_KEY, backend="memory")
    app = create_app(repos=build_memory_repositories(), settings=settings)
    return TestClient(app)


def test_health_is_open(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_auth_required(client):
    assert client.get("/workspaces").status_code == 401
    assert client.get("/workspaces", headers={"X-API-Key": "wrong"}).status_code == 401


def test_full_crud_flow(client):
    # Workspace
    ws = client.post("/workspaces", json={"name": "Acme", "kind": "client"}, headers=AUTH)
    assert ws.status_code == 201
    ws_id = ws.json()["id"]

    # Project
    proj = client.post(
        f"/workspaces/{ws_id}/projects",
        json={"name": "Spring launch", "goal": "Announce line", "target_modalities": ["image"]},
        headers=AUTH,
    )
    assert proj.status_code == 201
    proj_id = proj.json()["id"]
    assert proj.json()["workspace_id"] == ws_id

    # Asset
    asset = client.post(
        f"/workspaces/{ws_id}/assets",
        json={"project_id": proj_id, "name": "Hero image", "modality": "image"},
        headers=AUTH,
    )
    assert asset.status_code == 201
    asset_id = asset.json()["id"]

    # Version
    version = client.post(
        f"/workspaces/{ws_id}/versions",
        json={"asset_id": asset_id, "provider": "stub", "prompt": "a red bicycle"},
        headers=AUTH,
    )
    assert version.status_code == 201
    version_id = version.json()["id"]

    # List + filter
    listed = client.get(f"/workspaces/{ws_id}/versions?asset_id={asset_id}", headers=AUTH)
    assert [v["id"] for v in listed.json()] == [version_id]

    # Update review metadata
    patched = client.patch(
        f"/workspaces/{ws_id}/versions/{version_id}",
        json={"verdict": "pass", "status": "ready", "output_ref": "local://x.png"},
        headers=AUTH,
    )
    assert patched.json()["verdict"] == "pass"
    assert patched.json()["output_ref"] == "local://x.png"


def test_tenant_isolation_via_api(client):
    ws1 = client.post("/workspaces", json={"name": "One"}, headers=AUTH).json()["id"]
    ws2 = client.post("/workspaces", json={"name": "Two"}, headers=AUTH).json()["id"]
    proj = client.post(
        f"/workspaces/{ws1}/projects",
        json={"name": "P1", "goal": "g"},
        headers=AUTH,
    ).json()["id"]

    # Same project id, wrong workspace -> 404.
    assert client.get(f"/workspaces/{ws2}/projects/{proj}", headers=AUTH).status_code == 404
    assert client.get(f"/workspaces/{ws1}/projects/{proj}", headers=AUTH).status_code == 200


def test_create_project_in_missing_workspace_404(client):
    resp = client.post(
        "/workspaces/does-not-exist/projects",
        json={"name": "P", "goal": "g"},
        headers=AUTH,
    )
    assert resp.status_code == 404
