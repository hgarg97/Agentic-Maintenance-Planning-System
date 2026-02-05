"""
Graph Builder
=============
Constructs the LangGraph StateGraph, wires all nodes and edges,
and compiles with the PostgreSQL checkpointer.
"""

import logging

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from graph.state import MaintenanceState
from graph.nodes import (
    james_supervisor_node,
    david_supervisor_node,
    technician_hitl_node,
    mira_inventory_node,
    roberto_procurement_node,
    send_email_report_node,
)
from graph.edges import (
    route_from_james,
    route_from_david,
    route_from_technician,
    route_from_mira,
    route_from_roberto,
    route_from_email,
)

logger = logging.getLogger(__name__)


def build_graph() -> StateGraph:
    """
    Build the maintenance planning StateGraph (uncompiled).

    Graph topology:
        START -> james_supervisor
        james_supervisor -> {david, mira, roberto, email, END}
        david_supervisor -> {technician, mira, james}
        technician_hitl  -> {mira, david, james}
        mira_inventory   -> {roberto, technician, david, james}
        roberto_procure  -> {mira, james}
        send_email       -> james
    """
    graph = StateGraph(MaintenanceState)

    # ---- Add Nodes ----
    graph.add_node("james_supervisor", james_supervisor_node)
    graph.add_node("david_supervisor", david_supervisor_node)
    graph.add_node("technician_hitl", technician_hitl_node)
    graph.add_node("mira_inventory", mira_inventory_node)
    graph.add_node("roberto_procurement", roberto_procurement_node)
    graph.add_node("send_email_report", send_email_report_node)

    # ---- Entry Edge ----
    graph.add_edge(START, "james_supervisor")

    # ---- Conditional Edges from James ----
    graph.add_conditional_edges(
        "james_supervisor",
        route_from_james,
        {
            "david_supervisor": "david_supervisor",
            "mira_inventory": "mira_inventory",
            "roberto_procurement": "roberto_procurement",
            "send_email_report": "send_email_report",
            END: END,
        },
    )

    # ---- Conditional Edges from David ----
    graph.add_conditional_edges(
        "david_supervisor",
        route_from_david,
        {
            "technician_hitl": "technician_hitl",
            "mira_inventory": "mira_inventory",
            "james_supervisor": "james_supervisor",
        },
    )

    # ---- Conditional Edges from Technician ----
    graph.add_conditional_edges(
        "technician_hitl",
        route_from_technician,
        {
            "mira_inventory": "mira_inventory",
            "david_supervisor": "david_supervisor",
            "james_supervisor": "james_supervisor",
        },
    )

    # ---- Conditional Edges from Mira ----
    graph.add_conditional_edges(
        "mira_inventory",
        route_from_mira,
        {
            "roberto_procurement": "roberto_procurement",
            "technician_hitl": "technician_hitl",
            "david_supervisor": "david_supervisor",
            "james_supervisor": "james_supervisor",
        },
    )

    # ---- Conditional Edges from Roberto ----
    graph.add_conditional_edges(
        "roberto_procurement",
        route_from_roberto,
        {
            "mira_inventory": "mira_inventory",
            "james_supervisor": "james_supervisor",
        },
    )

    # ---- Email report always returns to James ----
    graph.add_edge("send_email_report", "james_supervisor")

    return graph


async def compile_graph(db_uri: str):
    """
    Compile the graph with a PostgreSQL-backed checkpointer.

    Args:
        db_uri: PostgreSQL connection URI

    Returns:
        Compiled graph and checkpointer (as a context manager)
    """
    graph = build_graph()

    # Create checkpointer
    checkpointer = AsyncPostgresSaver.from_conn_string(db_uri)
    await checkpointer.setup()

    compiled = graph.compile(checkpointer=checkpointer)
    logger.info("Maintenance planning graph compiled successfully")
    return compiled, checkpointer
