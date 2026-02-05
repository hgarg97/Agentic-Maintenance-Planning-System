"""
Graph State Schema
==================
Defines the MaintenanceState TypedDict - the shared state contract
between all agent nodes in the LangGraph orchestration.
"""

from typing import Annotated, Optional

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class MaintenanceState(TypedDict):
    """
    Shared state for the maintenance planning graph.
    All agent nodes read from and write to this state.
    """

    # ---- Message History (shared channel) ----
    messages: Annotated[list, add_messages]

    # ---- Routing / Control ----
    current_agent: str                          # Who is currently active
    next_agent: Optional[str]                   # Who to route to next
    user_intent: Optional[str]                  # Classified intent from James

    # ---- Ticket Context ----
    ticket_ids: Optional[list[int]]             # List of ticket IDs being processed
    current_ticket_id: Optional[int]            # Current ticket being worked on
    ticket_data: Optional[dict]                 # Current ticket full data
    machine_id: Optional[int]                   # Machine for current ticket

    # ---- Work Order Context ----
    work_order_id: Optional[int]                # Current work order ID
    work_order_number: Optional[str]            # Current work order number
    work_order_data: Optional[dict]             # Full work order data
    technician_id: Optional[int]                # Assigned technician

    # ---- Parts / Inventory Context ----
    required_parts: Optional[list[dict]]        # Parts needed for current WO
    parts_check_result: Optional[dict]          # Mira's inventory check result
    mismatched_parts: Optional[list[dict]]      # Parts not in machine BOM
    out_of_stock_parts: Optional[list[dict]]    # Parts that need procurement

    # ---- Procurement Context ----
    requisition_ids: Optional[list[int]]        # Active purchase requisition IDs
    procurement_status: Optional[str]           # Overall procurement status
    vendor_responses: Optional[list[dict]]      # Vendor response data

    # ---- HITL (Technician) Context ----
    hitl_action: Optional[str]                  # What action the technician took
    hitl_response: Optional[dict]               # Technician's parsed response

    # ---- Output ----
    final_summary: Optional[str]                # James's final response to user
    email_report: Optional[str]                 # Email report content
    agent_outputs: Optional[list[dict]]         # Accumulated agent outputs for display

    # ---- Iteration Control ----
    iteration_count: int                        # Track iterations to prevent loops
    max_iterations: int                         # Max allowed iterations
