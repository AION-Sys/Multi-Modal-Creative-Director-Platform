"""LangGraph assembly for the director pipeline.

Today it's a single Plan node — deliberately, so the Plan stage can be verified
in isolation before Generate/Critique/Review are wired in. Adding a stage later
is `add_node` + `add_edge`; the state and node contracts don't change.
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from ..providers.base import ProviderRegistry
from ..repositories.base import RepositorySet
from ..storage.base import ObjectStorage
from .director import DirectorAgent
from .nodes import make_critique_node, make_generate_node, make_plan_node
from .state import DirectorState


def build_plan_graph(director: DirectorAgent):
    """Compile a one-node graph: entry -> plan -> END."""
    graph = StateGraph(DirectorState)
    graph.add_node("plan", make_plan_node(director))
    graph.set_entry_point("plan")
    graph.add_edge("plan", END)
    return graph.compile()


def build_pipeline_graph(
    director: DirectorAgent,
    repos: RepositorySet,
    providers: ProviderRegistry,
    storage: ObjectStorage,
):
    """Compile the pipeline: entry -> plan -> generate -> critique -> END.

    Persists Assets and Versions as it goes, and annotates each generated Version
    with a pass/regenerate verdict. The Review stage (approve / regenerate loop)
    appends onto this same graph next.
    """
    graph = StateGraph(DirectorState)
    graph.add_node("plan", make_plan_node(director))
    graph.add_node("generate", make_generate_node(repos, providers, storage))
    graph.add_node("critique", make_critique_node(director, repos, storage))
    graph.set_entry_point("plan")
    graph.add_edge("plan", "generate")
    graph.add_edge("generate", "critique")
    graph.add_edge("critique", END)
    return graph.compile()
