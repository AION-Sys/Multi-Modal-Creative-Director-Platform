"""LangGraph assembly for the director pipeline.

Today it's a single Plan node — deliberately, so the Plan stage can be verified
in isolation before Generate/Critique/Review are wired in. Adding a stage later
is `add_node` + `add_edge`; the state and node contracts don't change.
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from .director import DirectorAgent
from .nodes import make_plan_node
from .state import DirectorState


def build_plan_graph(director: DirectorAgent):
    """Compile a one-node graph: entry -> plan -> END."""
    graph = StateGraph(DirectorState)
    graph.add_node("plan", make_plan_node(director))
    graph.set_entry_point("plan")
    graph.add_edge("plan", END)
    return graph.compile()
