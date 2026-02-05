"""
Agent Mira - Inventory Manager
================================
Full database access for inventory, parts, and maintenance queries.
- Checks stock levels against work order requirements
- Validates parts against machine BOM
- Issues parts from inventory
- Flags out-of-stock items for procurement by Roberto
- Handles ad-hoc database queries from James
"""

import logging

from langchain_core.messages import AIMessage, HumanMessage

from config.settings import AGENTS, MODELS
from config.prompts import MIRA_SYSTEM_PROMPT, MIRA_INVENTORY_CHECK_PROMPT, MIRA_QUERY_PROMPT
from graph.state import MaintenanceState
import services.llm_service as llm
from tools.db_tools import (
    check_inventory,
    check_part_in_bom,
    update_inventory,
    get_full_inventory,
    get_low_stock_parts,
    search_parts,
    get_bom_for_machine,
)
from tools.formatting_tools import format_inventory_table, format_bom_table

logger = logging.getLogger(__name__)


async def mira_node(state: MaintenanceState, config: dict) -> dict:
    """
    Mira's main node logic.
    Routes based on context: work order parts check vs. ad-hoc query.
    """
    cl_callback = config.get("configurable", {}).get("cl_callback")
    agent_callback = config.get("configurable", {}).get("agent_callback")
    iteration = state.get("iteration_count", 0)
    intent = state.get("user_intent")
    work_order_id = state.get("work_order_id")
    required_parts = state.get("required_parts")
    hitl_action = state.get("hitl_action")

    # Notify UI
    if agent_callback:
        await agent_callback("mira", "thinking")

    # ---- WORK ORDER PARTS CHECK ----
    if work_order_id and required_parts and hitl_action != "request_parts":
        return await _check_work_order_parts(state, config)

    # ---- TECHNICIAN PARTS REQUEST ----
    if hitl_action == "request_parts":
        return await _handle_technician_parts_request(state, config)

    # ---- AD-HOC INVENTORY/DATABASE QUERY ----
    if intent in ("inventory_query", "ticket_query", "priority_query"):
        return await _handle_database_query(state, config)

    # ---- DEFAULT: Answer based on context ----
    return await _handle_database_query(state, config)


async def _check_work_order_parts(
    state: MaintenanceState, config: dict
) -> dict:
    """Check parts availability for a work order."""
    cl_callback = config.get("configurable", {}).get("cl_callback")
    iteration = state.get("iteration_count", 0)
    required_parts = state.get("required_parts", [])
    machine_id = state.get("machine_id")
    work_order_number = state.get("work_order_number", "")

    available_parts = []
    out_of_stock = []
    mismatched = []

    intro = f"Checking inventory for work order **{work_order_number}**...\n\n"
    if cl_callback:
        for token in intro:
            await cl_callback(token, "mira")

    for part in required_parts:
        inv = await check_inventory.ainvoke({"part_id": part["part_id"]})

        if inv:
            stock = inv.get("quantity_on_hand", 0)
            needed = part.get("quantity_required", 1)

            if stock >= needed:
                available_parts.append(
                    {**part, "stock_on_hand": stock, "bin_location": inv.get("bin_location", "N/A"), "status": "available"}
                )
            else:
                out_of_stock.append(
                    {**part, "stock_on_hand": stock, "bin_location": inv.get("bin_location", "N/A"), "status": "out_of_stock"}
                )
        else:
            out_of_stock.append(
                {**part, "stock_on_hand": 0, "bin_location": "N/A", "status": "out_of_stock"}
            )

    # Build response
    result_msg = f"### Inventory Check for {work_order_number}\n\n"

    if available_parts:
        result_msg += f"**Available Parts ({len(available_parts)}):**\n\n"
        result_msg += "| Part # | Name | Needed | In Stock | Bin Location |\n"
        result_msg += "|--------|------|--------|----------|-------------|\n"
        for p in available_parts:
            result_msg += (
                f"| {p['part_number']} | {p['part_name']} | {p['quantity_required']} "
                f"| {p['stock_on_hand']} | {p.get('bin_location', 'N/A')} |\n"
            )
        result_msg += "\n"

    if out_of_stock:
        result_msg += f"**Out of Stock / Insufficient ({len(out_of_stock)}):**\n\n"
        result_msg += "| Part # | Name | Needed | In Stock | Action |\n"
        result_msg += "|--------|------|--------|----------|--------|\n"
        for p in out_of_stock:
            result_msg += (
                f"| {p['part_number']} | {p['part_name']} | {p['quantity_required']} "
                f"| {p['stock_on_hand']} | Procurement Required |\n"
            )
        result_msg += "\nI'll notify **Roberto** (Procurement) to source these parts from our vendors.\n"

    if not out_of_stock:
        result_msg += "\nAll parts are available. The technician can proceed with the work order.\n"

    if cl_callback:
        for token in result_msg:
            await cl_callback(token, "mira")

    # Determine next routing
    next_agent = "roberto" if out_of_stock else "technician"

    return {
        "messages": [AIMessage(content=result_msg)],
        "current_agent": "mira",
        "next_agent": next_agent,
        "parts_check_result": {
            "available": available_parts,
            "out_of_stock": out_of_stock,
            "mismatched": mismatched,
        },
        "out_of_stock_parts": out_of_stock if out_of_stock else None,
        "iteration_count": iteration + 1,
        "agent_outputs": (state.get("agent_outputs", []) or []) + [
            {"agent": "mira", "content": result_msg}
        ],
    }


async def _handle_technician_parts_request(
    state: MaintenanceState, config: dict
) -> dict:
    """Handle parts request from the human technician."""
    cl_callback = config.get("configurable", {}).get("cl_callback")
    iteration = state.get("iteration_count", 0)
    hitl_response = state.get("hitl_response", {})
    machine_id = state.get("machine_id")
    work_order_number = state.get("work_order_number", "")

    requested_parts = hitl_response.get("parts_requested", [])
    result_msg = f"### Parts Request Processing for {work_order_number}\n\n"

    available_parts = []
    out_of_stock = []
    mismatched = []

    for part_query in requested_parts:
        # Search for the part
        parts = await search_parts.ainvoke({"search_term": part_query})
        if not parts:
            result_msg += f"Could not find part matching: **{part_query}**\n"
            continue

        part = parts[0]  # Best match
        part_id = part["id"]

        # Check if part is in BOM for this machine
        if machine_id:
            bom_check = await check_part_in_bom.ainvoke(
                {"machine_id": machine_id, "part_id": part_id}
            )
            if not bom_check.get("in_bom"):
                mismatched.append(part)
                result_msg += (
                    f"**Warning:** Part **{part['part_number']}** ({part['name']}) "
                    f"is **not in the BOM** for this machine. This part is typically "
                    f"used for other machines. I'm processing your request, but please "
                    f"verify this is correct.\n\n"
                )

        # Check inventory
        stock = part.get("stock_on_hand", 0)
        if stock > 0:
            available_parts.append(
                {
                    "part_id": part_id,
                    "part_number": part["part_number"],
                    "part_name": part["name"],
                    "stock_on_hand": stock,
                    "bin_location": part.get("bin_location", "N/A"),
                    "quantity_required": 1,
                }
            )
            result_msg += (
                f"Part **{part['part_number']}** ({part['name']}) - "
                f"**Available** (Stock: {stock}, Bin: {part.get('bin_location', 'N/A')})\n"
            )
        else:
            out_of_stock.append(
                {
                    "part_id": part_id,
                    "part_number": part["part_number"],
                    "part_name": part["name"],
                    "stock_on_hand": 0,
                    "quantity_required": 1,
                }
            )
            result_msg += (
                f"Part **{part['part_number']}** ({part['name']}) - "
                f"**Out of Stock**. Will request procurement.\n"
            )

    if out_of_stock:
        result_msg += "\nI'll notify **Roberto** to source the missing parts.\n"

    if cl_callback:
        for token in result_msg:
            await cl_callback(token, "mira")

    next_agent = "roberto" if out_of_stock else "technician"

    return {
        "messages": [AIMessage(content=result_msg)],
        "current_agent": "mira",
        "next_agent": next_agent,
        "parts_check_result": {
            "available": available_parts,
            "out_of_stock": out_of_stock,
            "mismatched": mismatched,
        },
        "out_of_stock_parts": out_of_stock if out_of_stock else None,
        "mismatched_parts": mismatched if mismatched else None,
        "hitl_action": None,  # Clear HITL action
        "iteration_count": iteration + 1,
        "agent_outputs": (state.get("agent_outputs", []) or []) + [
            {"agent": "mira", "content": result_msg}
        ],
    }


async def _handle_database_query(
    state: MaintenanceState, config: dict
) -> dict:
    """Handle ad-hoc database queries from James or the user."""
    cl_callback = config.get("configurable", {}).get("cl_callback")
    iteration = state.get("iteration_count", 0)
    messages = state.get("messages", [])

    # Get the user's original query
    user_query = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            user_query = msg.content
            break

    # Fetch relevant data based on query
    inventory = await get_full_inventory.ainvoke({})
    low_stock = await get_low_stock_parts.ainvoke({})

    inventory_context = "Current Inventory:\n"
    for item in inventory:
        inventory_context += (
            f"- {item['part_number']}: {item['part_name']} | "
            f"Stock: {item['quantity_on_hand']} | "
            f"Reorder Level: {item['reorder_level']} | "
            f"Bin: {item.get('bin_location', 'N/A')} | "
            f"Status: {item.get('stock_status', 'unknown')}\n"
        )

    # Use LLM to generate a natural response
    llm_messages = [
        {"role": "system", "content": MIRA_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": MIRA_QUERY_PROMPT.format(query=user_query)
            + f"\n\nDatabase Context:\n{inventory_context}",
        },
    ]

    response_text = ""
    async for token in await llm.chat(
        messages=llm_messages,
        model=MODELS["main"],
        stream=True,
    ):
        response_text += token
        if cl_callback:
            await cl_callback(token, "mira")

    return {
        "messages": [AIMessage(content=response_text)],
        "current_agent": "mira",
        "next_agent": "james",
        "iteration_count": iteration + 1,
        "agent_outputs": (state.get("agent_outputs", []) or []) + [
            {"agent": "mira", "content": response_text}
        ],
    }
