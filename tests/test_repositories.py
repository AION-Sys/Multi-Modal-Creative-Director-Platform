"""Memory backend behavior + tenant isolation."""

import pytest

from creative_director.domain.models import Project, Workspace
from creative_director.repositories.factory import build_memory_repositories


@pytest.fixture
def repos():
    return build_memory_repositories()


async def test_create_and_get(repos):
    ws = await repos.workspaces.create(Workspace(name="Acme"))
    fetched = await repos.workspaces.get(ws.id)
    assert fetched is not None
    assert fetched.name == "Acme"


async def test_update_bumps_updated_at(repos):
    ws = await repos.workspaces.create(Workspace(name="Acme"))
    updated = await repos.workspaces.update(ws.id, {"name": "Acme Inc"})
    assert updated.name == "Acme Inc"
    assert updated.updated_at >= ws.updated_at


async def test_delete(repos):
    ws = await repos.workspaces.create(Workspace(name="Temp"))
    assert await repos.workspaces.delete(ws.id) is True
    assert await repos.workspaces.get(ws.id) is None
    assert await repos.workspaces.delete(ws.id) is False


async def test_returned_objects_are_copies(repos):
    ws = await repos.workspaces.create(Workspace(name="Acme"))
    ws.name = "Mutated locally"
    fresh = await repos.workspaces.get(ws.id)
    assert fresh.name == "Acme"  # store was not mutated


async def test_tenant_isolation_on_get_and_list(repos):
    ws1 = await repos.workspaces.create(Workspace(name="One"))
    ws2 = await repos.workspaces.create(Workspace(name="Two"))
    p1 = await repos.projects.create(
        Project(workspace_id=ws1.id, name="P1", goal="g")
    )
    await repos.projects.create(Project(workspace_id=ws2.id, name="P2", goal="g"))

    # Cross-workspace get is denied.
    assert await repos.projects.get(p1.id, workspace_id=ws2.id) is None
    assert await repos.projects.get(p1.id, workspace_id=ws1.id) is not None

    # List is scoped.
    ws1_projects = await repos.projects.list(workspace_id=ws1.id)
    assert [p.id for p in ws1_projects] == [p1.id]


async def test_list_filters(repos):
    ws = await repos.workspaces.create(Workspace(name="One"))
    pa = await repos.projects.create(Project(workspace_id=ws.id, name="A", goal="g"))
    pb = await repos.projects.create(Project(workspace_id=ws.id, name="B", goal="g"))
    filtered = await repos.projects.list(workspace_id=ws.id, filters={"name": "B"})
    assert [p.id for p in filtered] == [pb.id]
    assert {p.id for p in await repos.projects.list(workspace_id=ws.id)} == {pa.id, pb.id}
