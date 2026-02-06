"""
Graph Nodes
============
Thin wrapper functions that serve as entry points for the LangGraph StateGraph.
Each node imports its logic from the corresponding agent module.
This indirection provides a clean seam for testing and mocking.
"""

import sys
from pathlib import Path
from typing import Optional

from langchain_core.runnables import RunnableConfig

# Ensure the project root is in Python path for imports
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from graph.state import MaintenanceState

# Import agents at module level (after path is set)
from agents.james import james_node, send_email_report
from agents.david import david_node
from agents.technician import technician_node
from agents.mira import mira_node
from agents.roberto import roberto_node


async def james_supervisor_node(state: MaintenanceState, config: RunnableConfig) -> dict:
    """Entry point for Agent James (Supervisor/Orchestrator)."""
    return await james_node(state, config)


async def david_supervisor_node(state: MaintenanceState, config: RunnableConfig) -> dict:
    """Entry point for Agent David (Maintenance Supervisor)."""
    return await david_node(state, config)


async def technician_hitl_node(state: MaintenanceState, config: RunnableConfig) -> dict:
    """Entry point for Human Technician (Human-in-the-Loop)."""
    return await technician_node(state, config)


async def mira_inventory_node(state: MaintenanceState, config: RunnableConfig) -> dict:
    """Entry point for Agent Mira (Inventory Manager)."""
    return await mira_node(state, config)


async def roberto_procurement_node(state: MaintenanceState, config: RunnableConfig) -> dict:
    """Entry point for Agent Roberto (Procurement Agent)."""
    return await roberto_node(state, config)


async def send_email_report_node(state: MaintenanceState, config: RunnableConfig) -> dict:
    """Entry point for email report generation."""
    return await send_email_report(state, config)
