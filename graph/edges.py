"""
Graph Edges
============
Conditional routing functions that determine which node to visit next.
Each function reads the graph state and returns the name of the next node.
"""

import logging

from langgraph.graph import END

from graph.state import MaintenanceState

logger = logging.getLogger(__name__)


def route_from_james(state: MaintenanceState) -> str:
    """
    Route from James (supervisor) based on classified user intent or next_agent.

    Returns one of:
        - "david_supervisor"     : maintenance execution, work order tasks
        - "mira_inventory"       : inventory/database queries
        - "send_email_report"    : email report generation
        - END                    : direct answer to user (general Q&A, summary done)
    """
    next_agent = state.get("next_agent")
    intent = state.get("user_intent")

    # Check iteration limit
    if state.get("iteration_count", 0) >= state.get("max_iterations", 15):
        logger.warning("Max iterations reached, ending graph")
        return END

    # Explicit next_agent takes priority
    if next_agent:
        logger.info(f"James routing to explicit next_agent: {next_agent}")
        if next_agent == "david":
            return "david_supervisor"
        elif next_agent == "mira":
            return "mira_inventory"
        elif next_agent == "roberto":
            return "roberto_procurement"
        elif next_agent == "email":
            return "send_email_report"
        elif next_agent == "end":
            return END

    # Route based on classified intent
    if intent in ("execute_maintenance", "execute_single_ticket"):
        return "david_supervisor"
    elif intent in ("inventory_query", "ticket_query", "priority_query"):
        return "mira_inventory"
    elif intent == "email_report":
        return "send_email_report"
    else:
        # general_qa or unknown - James handles directly
        return END


def route_from_david(state: MaintenanceState) -> str:
    """
    Route from David (maintenance supervisor).

    Returns one of:
        - "technician_hitl"    : present work order to technician
        - "mira_inventory"     : check parts availability
        - "james_supervisor"   : report back to James
    """
    next_agent = state.get("next_agent")

    if next_agent == "technician":
        return "technician_hitl"
    elif next_agent == "mira":
        return "mira_inventory"
    elif next_agent == "james":
        return "james_supervisor"

    # Default: after creating work order, check parts with Mira
    if state.get("work_order_id") and not state.get("parts_check_result"):
        return "mira_inventory"

    # If parts checked and work order ready, go to technician
    if state.get("parts_check_result") and state.get("work_order_id"):
        return "technician_hitl"

    return "james_supervisor"


def route_from_technician(state: MaintenanceState) -> str:
    """
    Route from Human Technician (after interrupt resumes).

    Returns one of:
        - "mira_inventory"     : technician requested parts
        - "david_supervisor"   : technician rescheduled
        - "james_supervisor"   : technician confirmed completion
    """
    action = state.get("hitl_action")

    if action == "request_parts":
        return "mira_inventory"
    elif action == "reschedule":
        return "david_supervisor"
    elif action == "confirm_completion":
        return "james_supervisor"
    elif action == "add_notes":
        return "james_supervisor"

    # Default: report back to James
    return "james_supervisor"


def route_from_mira(state: MaintenanceState) -> str:
    """
    Route from Mira (inventory manager).

    Returns one of:
        - "roberto_procurement"  : parts out of stock, need to order
        - "technician_hitl"      : parts available, notify technician
        - "david_supervisor"     : parts status for work order
        - "james_supervisor"     : query answer or simple inventory response
    """
    next_agent = state.get("next_agent")

    if next_agent == "roberto":
        return "roberto_procurement"
    elif next_agent == "technician":
        return "technician_hitl"
    elif next_agent == "david":
        return "david_supervisor"
    elif next_agent == "james":
        return "james_supervisor"

    # If there are out-of-stock parts, route to Roberto
    out_of_stock = state.get("out_of_stock_parts")
    if out_of_stock:
        return "roberto_procurement"

    # If this was part of a work order flow, go back to technician
    if state.get("work_order_id") and state.get("hitl_action") == "request_parts":
        return "technician_hitl"

    # Default: report back to James
    return "james_supervisor"


def route_from_roberto(state: MaintenanceState) -> str:
    """
    Route from Roberto (procurement).

    Returns one of:
        - "mira_inventory"     : procurement complete, update inventory/status
        - "james_supervisor"   : report procurement status
    """
    next_agent = state.get("next_agent")

    if next_agent == "mira":
        return "mira_inventory"
    elif next_agent == "james":
        return "james_supervisor"

    # Default: report back to James with procurement status
    return "james_supervisor"


def route_from_email(state: MaintenanceState) -> str:
    """Route from email report node - always back to James."""
    return "james_supervisor"
