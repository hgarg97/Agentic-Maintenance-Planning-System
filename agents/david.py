"""
Agent David - Maintenance Supervisor
======================================
Manages work orders, assigns technicians, oversees maintenance execution.
- Receives maintenance tickets from James
- Creates work orders with required parts from BOM
- Assigns the best available technician
- Routes to technician (HITL) or Mira (inventory check)
"""

import logging
from datetime import date

from langchain_core.messages import AIMessage

from config.settings import AGENTS, MODELS
from config.prompts import DAVID_SYSTEM_PROMPT, DAVID_WORK_ORDER_PROMPT
from graph.state import MaintenanceState
import services.llm_service as llm
from tools.db_tools import (
    get_ticket_by_number,
    get_bom_for_machine,
    get_available_technicians,
    create_work_order,
    add_work_order_parts,
    update_ticket_status,
    get_work_order_details,
)
from tools.formatting_tools import format_work_order_card

logger = logging.getLogger(__name__)


async def david_node(state: MaintenanceState, config: dict) -> dict:
    """
    David's main node logic.
    Creates work orders, assigns technicians, and routes to next step.
    """
    cl_callback = config.get("configurable", {}).get("cl_callback")
    agent_callback = config.get("configurable", {}).get("agent_callback")
    iteration = state.get("iteration_count", 0)
    ticket_ids = state.get("ticket_ids", [])
    current_ticket_id = state.get("current_ticket_id")

    # Notify UI
    if agent_callback:
        await agent_callback("david", "thinking")

    # If we're receiving results back from technician/mira, just pass through
    if state.get("hitl_action") in ("confirm_completion", "reschedule"):
        return await _handle_post_technician(state, config)

    # Pick the next ticket to process
    if not current_ticket_id and ticket_ids:
        current_ticket_id = ticket_ids[0]

    if not current_ticket_id:
        msg = "No maintenance tickets to process at this time."
        if cl_callback:
            for token in msg:
                await cl_callback(token, "david")
        return {
            "messages": [AIMessage(content=msg)],
            "current_agent": "david",
            "next_agent": "james",
            "iteration_count": iteration + 1,
        }

    # Fetch ticket details
    from services.database import DatabaseService

    ticket = await DatabaseService.fetch_one(
        """
        SELECT mt.*, m.machine_code, m.name as machine_name, m.location,
               m.criticality, m.id as machine_id
        FROM maintenance_tickets mt
        JOIN machines m ON mt.machine_id = m.id
        WHERE mt.id = %s
        """,
        (current_ticket_id,),
    )

    if not ticket:
        return {
            "messages": [AIMessage(content=f"Ticket ID {current_ticket_id} not found.")],
            "current_agent": "david",
            "next_agent": "james",
            "iteration_count": iteration + 1,
        }

    machine_id = ticket["machine_id"]

    # Get BOM for the machine
    bom_parts = await get_bom_for_machine.ainvoke({"machine_id": machine_id})

    # Find available technician
    technicians = await get_available_technicians.ainvoke({"specialization": None})

    if not technicians:
        msg = f"No available technicians for ticket {ticket['ticket_number']}. All technicians are currently busy."
        if cl_callback:
            for token in msg:
                await cl_callback(token, "david")
        return {
            "messages": [AIMessage(content=msg)],
            "current_agent": "david",
            "next_agent": "james",
            "iteration_count": iteration + 1,
        }

    # Use LLM to generate work order procedures
    wo_response = await llm.chat(
        messages=[
            {"role": "system", "content": DAVID_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": DAVID_WORK_ORDER_PROMPT.format(
                    ticket=f"{ticket['ticket_number']}: {ticket['title']} - {ticket.get('description', '')}",
                    machine=f"{ticket['machine_name']} ({ticket['machine_code']}) at {ticket.get('location', 'N/A')}",
                    bom_parts="\n".join(
                        f"- {p['part_number']}: {p['part_name']} (qty: {p['quantity_required']}, "
                        f"stock: {p['stock_on_hand']}, critical: {p['is_critical']})"
                        for p in bom_parts
                    ),
                    technicians="\n".join(
                        f"- {t['name']} ({t['specialization']}, ID: {t['employee_id']})"
                        for t in technicians
                    ),
                ),
            },
        ],
        model=MODELS["main"],
        stream=False,
    )

    procedures = wo_response["content"]

    # Select best technician (first available, can be enhanced with specialization matching)
    selected_tech = technicians[0]

    # Create work order in DB
    wo = await create_work_order.ainvoke(
        {
            "ticket_id": current_ticket_id,
            "technician_id": selected_tech["id"],
            "description": f"{ticket['ticket_type']} - {ticket['title']}",
            "procedures": procedures,
            "scheduled_date": date.today().isoformat(),
            "estimated_hours": 2.0,
        }
    )

    # Add BOM parts to work order
    parts_to_add = [
        {
            "part_id": p["part_id"],
            "quantity_required": p["quantity_required"],
            "is_correct_for_machine": True,
        }
        for p in bom_parts
    ]
    if parts_to_add:
        await add_work_order_parts.ainvoke(
            {"work_order_id": wo["id"], "parts": parts_to_add}
        )

    # Get full work order details for display
    wo_details = await get_work_order_details.ainvoke({"work_order_id": wo["id"]})

    # Build display message
    intro = (
        f"I've created **Work Order {wo['work_order_number']}** for ticket "
        f"**{ticket['ticket_number']}** ({ticket['ticket_type']}).\n\n"
        f"**Assigned to:** {selected_tech['name']} ({selected_tech['specialization']})\n\n"
    )

    wo_card = format_work_order_card(wo_details)
    full_msg = intro + wo_card

    # Stream to UI
    if cl_callback:
        for token in intro:
            await cl_callback(token, "david")

    # Build the required_parts list for Mira
    required_parts = [
        {
            "part_id": p["part_id"],
            "part_number": p["part_number"],
            "part_name": p["part_name"],
            "quantity_required": p["quantity_required"],
            "stock_on_hand": p["stock_on_hand"],
        }
        for p in bom_parts
    ]

    return {
        "messages": [AIMessage(content=full_msg)],
        "current_agent": "david",
        "next_agent": "mira",  # Check parts availability with Mira
        "current_ticket_id": current_ticket_id,
        "machine_id": machine_id,
        "work_order_id": wo["id"],
        "work_order_number": wo["work_order_number"],
        "work_order_data": wo_details,
        "technician_id": selected_tech["id"],
        "required_parts": required_parts,
        "ticket_data": ticket,
        "iteration_count": iteration + 1,
        "agent_outputs": (state.get("agent_outputs", []) or []) + [
            {"agent": "david", "content": full_msg}
        ],
    }


async def _handle_post_technician(state: MaintenanceState, config: dict) -> dict:
    """Handle results coming back from the technician."""
    cl_callback = config.get("configurable", {}).get("cl_callback")
    iteration = state.get("iteration_count", 0)
    action = state.get("hitl_action")
    work_order_id = state.get("work_order_id")

    if action == "confirm_completion":
        from tools.db_tools import update_work_order_status, update_ticket_status

        # Mark work order as completed
        await update_work_order_status.ainvoke(
            {
                "work_order_id": work_order_id,
                "new_status": "completed",
                "technician_notes": "Work completed by technician.",
            }
        )

        # Mark ticket as completed
        ticket_id = state.get("current_ticket_id")
        if ticket_id:
            await update_ticket_status.ainvoke(
                {
                    "ticket_id": ticket_id,
                    "new_status": "completed",
                    "notes": f"Completed via WO {state.get('work_order_number')}",
                }
            )

        msg = f"Work order **{state.get('work_order_number')}** has been marked as **completed**. Great work!"
        if cl_callback:
            for token in msg:
                await cl_callback(token, "david")

        return {
            "messages": [AIMessage(content=msg)],
            "current_agent": "david",
            "next_agent": "james",
            "iteration_count": iteration + 1,
            "agent_outputs": (state.get("agent_outputs", []) or []) + [
                {"agent": "david", "content": msg}
            ],
        }

    elif action == "reschedule":
        from tools.db_tools import update_work_order_status

        await update_work_order_status.ainvoke(
            {
                "work_order_id": work_order_id,
                "new_status": "waiting_parts",
                "technician_notes": "Rescheduled - awaiting parts or conditions.",
            }
        )

        msg = (
            f"Work order **{state.get('work_order_number')}** has been **rescheduled**. "
            f"It will be revisited when parts are available or conditions are met."
        )
        if cl_callback:
            for token in msg:
                await cl_callback(token, "david")

        return {
            "messages": [AIMessage(content=msg)],
            "current_agent": "david",
            "next_agent": "james",
            "iteration_count": iteration + 1,
            "agent_outputs": (state.get("agent_outputs", []) or []) + [
                {"agent": "david", "content": msg}
            ],
        }

    # Default pass through
    return {
        "current_agent": "david",
        "next_agent": "james",
        "iteration_count": iteration + 1,
    }
