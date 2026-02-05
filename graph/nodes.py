"""
Graph Nodes
============
Thin wrapper functions that serve as entry points for the LangGraph StateGraph.
Each node imports its logic from the corresponding agent module.
This indirection provides a clean seam for testing and mocking.
"""

from graph.state import MaintenanceState


async def james_supervisor_node(state: MaintenanceState, config: dict) -> dict:
    """Entry point for Agent James (Supervisor/Orchestrator)."""
    from agents.james import james_node
    return await james_node(state, config)


async def david_supervisor_node(state: MaintenanceState, config: dict) -> dict:
    """Entry point for Agent David (Maintenance Supervisor)."""
    from agents.david import david_node
    return await david_node(state, config)


async def technician_hitl_node(state: MaintenanceState, config: dict) -> dict:
    """Entry point for Human Technician (Human-in-the-Loop)."""
    from agents.technician import technician_node
    return await technician_node(state, config)


async def mira_inventory_node(state: MaintenanceState, config: dict) -> dict:
    """Entry point for Agent Mira (Inventory Manager)."""
    from agents.mira import mira_node
    return await mira_node(state, config)


async def roberto_procurement_node(state: MaintenanceState, config: dict) -> dict:
    """Entry point for Agent Roberto (Procurement Agent)."""
    from agents.roberto import roberto_node
    return await roberto_node(state, config)


async def send_email_report_node(state: MaintenanceState, config: dict) -> dict:
    """Entry point for email report generation."""
    from agents.james import send_email_report
    return await send_email_report(state, config)
