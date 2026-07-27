"""Review endpoints end-to-end through FastAPI, keyless stack."""

import pytest
from fastapi.testclient import TestClient

from creative_director.api.app import create_app
from creative_director.config import Settings
from creative_director.orchestration import FakeDirector
from creative_director.providers import build_provider_registry
from creative_director.repositories.factory import build_memory_repositories
from creative_director.storage import LocalStorage

API_KEY = "test-key"
AUTH = {"X-API-Key": API_KEY}


@pytest.fixture
def client(tmp_path):
    settings = Settings(_env_file=None, app_api_key=API_KEY, backend="memory")
    app = create_app(
        repos=build_memory_repositories(),
        settings=settings,
        director=FakeDirector(),
        providers=build_provider_registry(Settings(_env_file=None, image_provider="stub")),
        storage=LocalStorage(tmp_path),
    )
    return TestClient(app)


def _workspace_and_project(client):
    ws = client.post("/workspaces", json={"name": "Acme"}, headers=AUTH).json()["id"]
    proj = client.post(
        f"/workspaces/{ws}/projects",
        json={"name": "Launch", "goal": "Ship spring line",
              "target_modalities": ["image", "copy"]},
        headers=AUTH,
    ).json()["id"]
    return ws, proj


def test_run_review_approve_flow(client):
    ws, proj = _workspace_and_project(client)

    # Run the pipeline.
    run = client.post(f"/workspaces/{ws}/projects/{proj}/run", headers=AUTH)
    assert run.status_code == 200
    body = run.json()
    assert body["status"] == "awaiting_review"
    statuses = sorted(g["status"] for g in body["generated"])
    assert statuses == ["generated", "skipped"]

    # One asset awaits review (the image).
    review = client.get(f"/workspaces/{ws}/review?project_id={proj}", headers=AUTH)
    items = review.json()
    assert len(items) == 1
    assert items[0]["asset"]["modality"] == "image"
    version_id = items[0]["version"]["id"]

    # Approve it — asset locks, no longer pending.
    approved = client.post(f"/workspaces/{ws}/versions/{version_id}/approve", headers=AUTH)
    assert approved.json()["status"] == "approved"
    assert client.get(f"/workspaces/{ws}/review?project_id={proj}", headers=AUTH).json() == []


def test_regenerate_endpoint_branches_version(client):
    ws, proj = _workspace_and_project(client)
    client.post(f"/workspaces/{ws}/projects/{proj}/run", headers=AUTH)
    items = client.get(f"/workspaces/{ws}/review?project_id={proj}", headers=AUTH).json()
    asset_id = items[0]["asset"]["id"]
    v1 = items[0]["version"]["id"]

    resp = client.post(
        f"/workspaces/{ws}/assets/{asset_id}/regenerate",
        json={"prompt_suffix": "warmer palette"},
        headers=AUTH,
    )
    assert resp.status_code == 200
    out = resp.json()
    assert out["status"] == "generated"
    assert out["parent_version_id"] == v1
    assert out["version_id"] != v1


def test_reject_endpoint(client):
    ws, proj = _workspace_and_project(client)
    client.post(f"/workspaces/{ws}/projects/{proj}/run", headers=AUTH)
    items = client.get(f"/workspaces/{ws}/review?project_id={proj}", headers=AUTH).json()
    asset_id = items[0]["asset"]["id"]

    resp = client.post(f"/workspaces/{ws}/assets/{asset_id}/reject", headers=AUTH)
    assert resp.json()["status"] == "rejected"


def test_review_endpoints_require_auth(client):
    ws, proj = _workspace_and_project(client)
    assert client.post(f"/workspaces/{ws}/projects/{proj}/run").status_code == 401
    assert client.get(f"/workspaces/{ws}/review").status_code == 401


def test_run_missing_project_404(client):
    ws = client.post("/workspaces", json={"name": "Acme"}, headers=AUTH).json()["id"]
    resp = client.post(f"/workspaces/{ws}/projects/does-not-exist/run", headers=AUTH)
    assert resp.status_code == 404
