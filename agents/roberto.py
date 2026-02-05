"""
Agent Roberto - Procurement Agent
====================================
Handles vendor communication, purchase requisitions, and parts ordering.
- Contacts vendors via email (VendorA first, VendorB as fallback)
- Polls Gmail IMAP for vendor responses
- Parses vendor emails with GPT-4o-mini
- Updates procurement status in the database
"""

import logging

from langchain_core.messages import AIMessage

from config.settings import AGENTS, MODELS
from config.prompts import ROBERTO_SYSTEM_PROMPT, ROBERTO_PARSE_EMAIL_PROMPT
from graph.state import MaintenanceState
import services.llm_service as llm
from tools.db_tools import (
    get_vendors_by_priority,
    create_purchase_requisition,
    update_purchase_requisition,
)
from tools.email_tools import send_vendor_quote_request, poll_vendor_response
from tools.formatting_tools import format_procurement_status

logger = logging.getLogger(__name__)


async def roberto_node(state: MaintenanceState, config: dict) -> dict:
    """
    Roberto's main node logic.
    Creates purchase requisitions and contacts vendors for out-of-stock parts.
    """
    cl_callback = config.get("configurable", {}).get("cl_callback")
    agent_callback = config.get("configurable", {}).get("agent_callback")
    iteration = state.get("iteration_count", 0)
    out_of_stock = state.get("out_of_stock_parts", [])
    work_order_id = state.get("work_order_id")

    # Notify UI
    if agent_callback:
        await agent_callback("roberto", "thinking")

    if not out_of_stock:
        msg = "No parts require procurement at this time."
        if cl_callback:
            for token in msg:
                await cl_callback(token, "roberto")
        return {
            "messages": [AIMessage(content=msg)],
            "current_agent": "roberto",
            "next_agent": "james",
            "iteration_count": iteration + 1,
        }

    # Get vendors sorted by priority
    vendors = await get_vendors_by_priority.ainvoke({})
    if not vendors:
        msg = "No active vendors found in the system. Cannot proceed with procurement."
        return {
            "messages": [AIMessage(content=msg)],
            "current_agent": "roberto",
            "next_agent": "james",
            "iteration_count": iteration + 1,
        }

    intro = (
        f"I've identified **{len(out_of_stock)}** part(s) that need to be procured. "
        f"Let me reach out to our vendors.\n\n"
    )
    if cl_callback:
        for token in intro:
            await cl_callback(token, "roberto")

    results_msg = intro
    procurement_results = []

    for part in out_of_stock:
        part_result = await _procure_part(
            part=part,
            vendors=vendors,
            work_order_id=work_order_id,
            config=config,
        )
        procurement_results.append(part_result)
        results_msg += part_result["message"] + "\n"

    # Summary
    ordered = [r for r in procurement_results if r["status"] == "ordered"]
    failed = [r for r in procurement_results if r["status"] == "failed"]

    summary = f"\n### Procurement Summary\n"
    summary += f"- **Ordered:** {len(ordered)} part(s)\n"
    if failed:
        summary += f"- **Failed:** {len(failed)} part(s) - no vendor available\n"

    results_msg += summary

    if cl_callback:
        for token in summary:
            await cl_callback(token, "roberto")

    # Determine next step
    # If parts were ordered, we go back to mira to update the status
    next_agent = "james"

    return {
        "messages": [AIMessage(content=results_msg)],
        "current_agent": "roberto",
        "next_agent": next_agent,
        "procurement_status": "completed",
        "vendor_responses": procurement_results,
        "out_of_stock_parts": None,  # Clear after processing
        "iteration_count": iteration + 1,
        "agent_outputs": (state.get("agent_outputs", []) or []) + [
            {"agent": "roberto", "content": results_msg}
        ],
    }


async def _procure_part(
    part: dict,
    vendors: list[dict],
    work_order_id: int,
    config: dict,
) -> dict:
    """
    Attempt to procure a single part by contacting vendors in priority order.
    """
    cl_callback = config.get("configurable", {}).get("cl_callback")
    part_number = part.get("part_number", "")
    part_name = part.get("part_name", "")
    quantity = part.get("quantity_required", 1)
    part_id = part.get("part_id")

    for vendor in vendors:
        vendor_name = vendor["name"]
        vendor_email = vendor["email"]
        vendor_id = vendor["id"]

        status_msg = f"Contacting **{vendor_name}** for {part_name} ({part_number})...\n"
        if cl_callback:
            for token in status_msg:
                await cl_callback(token, "roberto")

        # Create purchase requisition
        requisition = await create_purchase_requisition.ainvoke(
            {
                "work_order_id": work_order_id,
                "part_id": part_id,
                "quantity": quantity,
                "vendor_id": vendor_id,
            }
        )

        req_number = requisition.get("requisition_number", "PR-UNKNOWN")

        # Send email to vendor
        email_result = await send_vendor_quote_request.ainvoke(
            {
                "vendor_email": vendor_email,
                "vendor_name": vendor_name,
                "part_number": part_number,
                "part_name": part_name,
                "quantity": quantity,
                "requisition_number": req_number,
                "urgency": "urgent",
            }
        )

        if email_result.get("status") != "sent":
            # Email failed, try next vendor
            status_msg = f"Failed to send email to {vendor_name}. Trying next vendor...\n"
            if cl_callback:
                for token in status_msg:
                    await cl_callback(token, "roberto")
            continue

        waiting_msg = f"Email sent to {vendor_name}. Waiting for response...\n"
        if cl_callback:
            for token in waiting_msg:
                await cl_callback(token, "roberto")

        # Poll for vendor response
        vendor_reply = await poll_vendor_response.ainvoke(
            {
                "requisition_number": req_number,
                "timeout_minutes": 5,  # Shorter for demo
            }
        )

        if vendor_reply:
            # Parse vendor response with LLM
            parsed = await llm.parse_json_response(
                vendor_reply.get("body", ""),
                ROBERTO_PARSE_EMAIL_PROMPT.format(
                    email_body=vendor_reply.get("body", "")
                ),
            )

            vendor_status = parsed.get("status", "")
            delivery_date = parsed.get("delivery_date", "")
            unit_price = parsed.get("unit_price")
            delivery_days = parsed.get("delivery_days")

            if vendor_status == "accepted":
                # Update requisition with vendor response
                await update_purchase_requisition.ainvoke(
                    {
                        "requisition_id": requisition["id"],
                        "status": "ordered",
                        "quoted_price": unit_price,
                        "expected_delivery": delivery_date,
                        "vendor_response": vendor_reply.get("body", ""),
                    }
                )

                result_msg = (
                    f"**{vendor_name}** accepted! Part **{part_number}** ({part_name})\n"
                    f"- Quantity: {quantity}\n"
                    f"- Price: ${unit_price or 'TBD'}\n"
                    f"- Expected Delivery: {delivery_date or f'{delivery_days} days'}\n"
                    f"- Requisition: {req_number}\n"
                )
                if cl_callback:
                    for token in result_msg:
                        await cl_callback(token, "roberto")

                return {
                    "status": "ordered",
                    "vendor": vendor_name,
                    "requisition_number": req_number,
                    "delivery_date": delivery_date,
                    "message": result_msg,
                }

            elif vendor_status == "declined":
                decline_msg = f"**{vendor_name}** declined the request. Trying next vendor...\n"
                if cl_callback:
                    for token in decline_msg:
                        await cl_callback(token, "roberto")

                # Update requisition
                await update_purchase_requisition.ainvoke(
                    {
                        "requisition_id": requisition["id"],
                        "status": "cancelled",
                        "vendor_response": vendor_reply.get("body", ""),
                    }
                )
                continue
        else:
            # Timeout - try next vendor
            timeout_msg = f"No response from **{vendor_name}** within timeout. Trying next vendor...\n"
            if cl_callback:
                for token in timeout_msg:
                    await cl_callback(token, "roberto")

            await update_purchase_requisition.ainvoke(
                {
                    "requisition_id": requisition["id"],
                    "status": "cancelled",
                    "vendor_response": "No response within timeout",
                }
            )
            continue

    # All vendors exhausted
    fail_msg = (
        f"**No vendor available** for part **{part_number}** ({part_name}). "
        f"All vendors either declined or did not respond.\n"
    )
    if cl_callback:
        for token in fail_msg:
            await cl_callback(token, "roberto")

    return {
        "status": "failed",
        "vendor": None,
        "message": fail_msg,
    }
