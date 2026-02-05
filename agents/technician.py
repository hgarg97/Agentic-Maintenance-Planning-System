"""
Agent Technician - Human-in-the-Loop
=======================================
Pauses the graph for human input using LangGraph's interrupt().
Presents work orders to the human technician and captures their response.
"""

import logging

from langchain_core.messages import AIMessage
from langgraph.types import interrupt

from config.settings import AGENTS, MODELS
from config.prompts import TECHNICIAN_PARSE_PROMPT
from graph.state import MaintenanceState
import services.llm_service as llm
from tools.formatting_tools import format_work_order_card

logger = logging.getLogger(__name__)


async def technician_node(state: MaintenanceState, config: dict) -> dict:
    """
    Human Technician node - pauses the graph for human input.

    Uses LangGraph's interrupt() to pause execution.
    The Chainlit app.py detects the interrupt, presents the work order card
    with action buttons, and resumes the graph with Command(resume=response).
    """
    cl_callback = config.get("configurable", {}).get("cl_callback")
    agent_callback = config.get("configurable", {}).get("agent_callback")
    iteration = state.get("iteration_count", 0)
    work_order_data = state.get("work_order_data", {})
    parts_check = state.get("parts_check_result", {})

    # Notify UI
    if agent_callback:
        await agent_callback("technician", "active")

    # Build the work order display payload for the human
    work_order_payload = {
        "work_order_number": state.get("work_order_number", ""),
        "work_order_id": state.get("work_order_id"),
        "ticket_number": work_order_data.get("ticket_number", ""),
        "ticket_type": work_order_data.get("ticket_type", ""),
        "machine_name": work_order_data.get("machine_name", ""),
        "machine_code": work_order_data.get("machine_code", ""),
        "location": work_order_data.get("location", ""),
        "priority": work_order_data.get("priority", ""),
        "description": work_order_data.get("description", ""),
        "procedures": work_order_data.get("procedures", ""),
        "technician_name": work_order_data.get("technician_name", ""),
        "parts": work_order_data.get("parts", []),
        "parts_available": parts_check.get("available", []),
        "parts_out_of_stock": parts_check.get("out_of_stock", []),
        "parts_mismatched": parts_check.get("mismatched", []),
        "status": work_order_data.get("status", "assigned"),
    }

    # Build a display message about available parts
    parts_msg = _build_parts_status_message(parts_check)

    # ---- INTERRUPT: Pause for human input ----
    # The graph stops here and returns the payload to Chainlit.
    # Chainlit displays the work order card and action buttons.
    # When the human responds, Chainlit resumes with Command(resume={...})
    technician_response = interrupt(work_order_payload)

    # ---- RESUMED: Process the technician's response ----
    logger.info(f"Technician responded: {technician_response}")

    # Parse the response
    action = technician_response.get("action", "")
    response_text = technician_response.get("text", "")
    parts_requested = technician_response.get("parts_requested", [])

    # If the response includes free text, parse it with LLM
    if response_text and not action:
        parsed = await llm.parse_json_response(
            response_text,
            TECHNICIAN_PARSE_PROMPT.format(
                input=response_text,
                work_order=state.get("work_order_number", ""),
                machine=work_order_data.get("machine_name", ""),
                parts=", ".join(
                    p.get("part_name", "") for p in work_order_data.get("parts", [])
                ),
            ),
        )
        action = parsed.get("action", "add_notes")
        parts_requested = parsed.get("parts_requested", parts_requested)
        notes = parsed.get("notes", response_text)
    else:
        notes = response_text

    # Build confirmation message
    if action == "confirm_completion":
        confirm_msg = (
            f"Technician has confirmed that work order **{state.get('work_order_number')}** "
            f"is **completed**. Updating records."
        )
    elif action == "request_parts":
        confirm_msg = (
            f"Technician has requested the following parts: "
            f"**{', '.join(parts_requested)}**. Forwarding to Mira for processing."
        )
    elif action == "reschedule":
        confirm_msg = (
            f"Technician has requested to **reschedule** work order "
            f"**{state.get('work_order_number')}**. Updating records."
        )
    elif action == "add_notes":
        confirm_msg = (
            f"Technician notes: {notes}\n"
            f"Notes added to work order **{state.get('work_order_number')}**."
        )
    else:
        confirm_msg = f"Technician response received: {response_text}"
        action = "add_notes"

    if cl_callback:
        for token in confirm_msg:
            await cl_callback(token, "technician")

    return {
        "messages": [AIMessage(content=confirm_msg)],
        "current_agent": "technician",
        "hitl_action": action,
        "hitl_response": {
            "action": action,
            "parts_requested": parts_requested,
            "notes": notes,
            "text": response_text,
        },
        "iteration_count": iteration + 1,
        "agent_outputs": (state.get("agent_outputs", []) or []) + [
            {"agent": "technician", "content": confirm_msg}
        ],
    }


def _build_parts_status_message(parts_check: dict) -> str:
    """Build a human-readable parts status message."""
    msg = ""
    available = parts_check.get("available", [])
    out_of_stock = parts_check.get("out_of_stock", [])
    mismatched = parts_check.get("mismatched", [])

    if available:
        msg += "**Parts Ready for Pickup:**\n"
        for p in available:
            msg += f"- {p.get('part_number', '')}: {p.get('part_name', '')} (Bin: {p.get('bin_location', 'N/A')})\n"
        msg += "\n"

    if out_of_stock:
        msg += "**Parts Being Procured:**\n"
        for p in out_of_stock:
            msg += f"- {p.get('part_number', '')}: {p.get('part_name', '')} (Procurement in progress)\n"
        msg += "\n"

    if mismatched:
        msg += "**Parts Not in BOM (Warning):**\n"
        for p in mismatched:
            msg += f"- {p.get('part_number', '')}: {p.get('name', '')} (Not standard for this machine)\n"
        msg += "\n"

    return msg
