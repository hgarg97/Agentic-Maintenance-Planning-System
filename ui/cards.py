"""
UI Cards
========
Chainlit-specific card builders that create rich interactive displays.
These extend the formatting_tools with Chainlit-specific elements.
"""

import chainlit as cl

from config.settings import AGENTS
from tools.formatting_tools import format_work_order_card as _format_wo_card


async def display_work_order_card(
    work_order_payload: dict,
) -> None:
    """
    Display a work order card in the chat with action buttons.
    Used when the graph hits the technician HITL interrupt.
    """
    wo_number = work_order_payload.get("work_order_number", "N/A")
    machine = work_order_payload.get("machine_name", "Unknown")
    machine_code = work_order_payload.get("machine_code", "")
    priority = work_order_payload.get("priority", "medium")
    description = work_order_payload.get("description", "")
    procedures = work_order_payload.get("procedures", "")
    technician = work_order_payload.get("technician_name", "Unassigned")

    # Build parts table
    parts = work_order_payload.get("parts", [])
    available = work_order_payload.get("parts_available", [])
    out_of_stock = work_order_payload.get("parts_out_of_stock", [])

    priority_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(
        priority, "⚪"
    )

    # Main work order card
    card = f"""## Work Order: {wo_number}

| Field | Details |
|-------|---------|
| **Machine** | {machine} ({machine_code}) |
| **Priority** | {priority_icon} {priority.upper()} |
| **Technician** | {technician} |
| **Description** | {description[:200]}{'...' if len(description) > 200 else ''} |

"""

    # Parts status
    if available:
        card += "### Parts Ready for Pickup\n\n"
        card += "| Part # | Name | Qty | Bin Location |\n"
        card += "|--------|------|-----|--------------|\n"
        for p in available:
            card += f"| {p.get('part_number', '')} | {p.get('part_name', '')} | {p.get('quantity_required', 1)} | {p.get('bin_location', 'N/A')} |\n"
        card += "\n"

    if out_of_stock:
        card += "### Parts Being Procured\n\n"
        card += "| Part # | Name | Qty | Status |\n"
        card += "|--------|------|-----|--------|\n"
        for p in out_of_stock:
            card += f"| {p.get('part_number', '')} | {p.get('part_name', '')} | {p.get('quantity_required', 1)} | Procurement in progress |\n"
        card += "\n"

    if procedures:
        card += f"### Procedures\n\n{procedures}\n"

    # Send the card as the technician
    await cl.Message(
        content=card,
        author=AGENTS["technician"]["name"],
    ).send()


async def display_technician_actions() -> dict:
    """
    Display action buttons for the technician and wait for response.

    Returns:
        dict with action and optional text
    """
    actions = [
        cl.Action(
            name="confirm_completion",
            payload={"action": "confirm_completion"},
            label="Work Completed",
            description="Mark this work order as completed",
        ),
        cl.Action(
            name="request_parts",
            payload={"action": "request_parts"},
            label="Request Parts",
            description="Request additional parts for this work order",
        ),
        cl.Action(
            name="reschedule",
            payload={"action": "reschedule"},
            label="Reschedule",
            description="Reschedule this work order for later",
        ),
        cl.Action(
            name="add_notes",
            payload={"action": "add_notes"},
            label="Add Notes",
            description="Add observations or notes to this work order",
        ),
    ]

    response = await cl.AskActionMessage(
        content="**Technician Action Required:** What would you like to do with this work order?",
        actions=actions,
        author=AGENTS["technician"]["name"],
        timeout=300,  # 5 minute timeout
    ).send()

    if response:
        return response.get("payload", {"action": "add_notes"})

    return {"action": "add_notes"}


async def get_technician_text_input(prompt: str) -> str:
    """
    Get free-text input from the technician.

    Args:
        prompt: The prompt to display

    Returns:
        The technician's text response
    """
    response = await cl.AskUserMessage(
        content=prompt,
        author=AGENTS["technician"]["name"],
        timeout=300,
    ).send()

    if response:
        return response.get("output", "")
    return ""


async def display_agent_thinking(agent_key: str, thinking_text: str) -> None:
    """
    Display an agent's thinking process in a collapsible step.
    """
    agent = AGENTS.get(agent_key, AGENTS["system"])

    async with cl.Step(
        name=f"{agent['name']} - {agent['role']}",
        type="tool",
    ) as step:
        step.output = thinking_text


async def display_status_update(
    agent_key: str, status: str, details: str = ""
) -> None:
    """Display a status update from an agent."""
    agent = AGENTS.get(agent_key, AGENTS["system"])
    content = f"**Status:** {status}"
    if details:
        content += f"\n{details}"

    await cl.Message(
        content=content,
        author=agent["name"],
    ).send()
