"""Run a project's brief through the director pipeline and record the run.

Builds a PlanBrief from the persisted Project (+ Workspace brand config), invokes
the plan -> generate -> critique graph, moves the Project to `review`, and writes
a PipelineRun capturing where the pipeline paused. The PipelineRun is the record
the review endpoints act on and the seed for resumability.
"""

from __future__ import annotations

from ..domain.enums import PipelineNode, PipelineStatus, ProjectStatus
from ..domain.models import PipelineRun
from ..orchestration.director import DirectorAgent, PlanBrief
from ..orchestration.graph import build_pipeline_graph
from ..providers.base import ProviderRegistry
from ..repositories.base import RepositorySet
from ..storage.base import ObjectStorage


class PipelineError(Exception):
    pass


async def run_project(
    director: DirectorAgent,
    repos: RepositorySet,
    providers: ProviderRegistry,
    storage: ObjectStorage,
    workspace_id: str,
    project_id: str,
) -> dict:
    project = await repos.projects.get(project_id, workspace_id=workspace_id)
    if project is None:
        raise PipelineError(f"Project {project_id} not found")
    workspace = await repos.workspaces.get(workspace_id)

    brief = PlanBrief(
        goal=project.goal,
        target_modalities=project.target_modalities,
        constraints=project.constraints,
        brand_config=workspace.brand_config if workspace else {},
        project_name=project.name,
        workspace_name=workspace.name if workspace else "",
    )

    graph = build_pipeline_graph(director, repos, providers, storage)
    state = await graph.ainvoke(
        {"brief": brief, "workspace_id": workspace_id, "project_id": project_id}
    )

    if state.get("error"):
        run = await repos.pipeline_runs.create(
            PipelineRun(
                workspace_id=workspace_id, project_id=project_id,
                current_node=PipelineNode.PLAN, status=PipelineStatus.FAILED,
                error=state["error"],
            )
        )
        return {"run_id": run.id, "status": "failed", "error": state["error"]}

    plan = state.get("plan")
    # Keep the persisted graph_state JSON-safe (no dataclasses / bytes).
    graph_state = {
        "plan_summary": plan.summary if plan else "",
        "planned_assets": state.get("planned_assets", []),
        "generated": state.get("generated", []),
        "critiques": state.get("critiques", []),
    }
    run = await repos.pipeline_runs.create(
        PipelineRun(
            workspace_id=workspace_id, project_id=project_id,
            current_node=PipelineNode.REVIEW, status=PipelineStatus.AWAITING_REVIEW,
            graph_state=graph_state,
        )
    )
    await repos.projects.update(
        project_id, {"status": ProjectStatus.REVIEW.value}, workspace_id=workspace_id
    )
    return {
        "run_id": run.id,
        "status": "awaiting_review",
        "plan_summary": graph_state["plan_summary"],
        "generated": graph_state["generated"],
        "critiques": graph_state["critiques"],
    }
