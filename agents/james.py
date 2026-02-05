"""
Agent James - Maintenance Planner (Supervisor/Orchestrator)
============================================================
The primary supervisor of the entire system.
- Classifies user intent and routes to appropriate sub-agents
- Generates final summaries from team results
- Handles general Q&A about maintenance tasks
- Composes and sends email reports
"""

import logging
from datetime import date

from langchain_core.messages import AIMessage, HumanMessage

from config.settings import AGENTS, INTENT_CATEGORIES, MODELS
from config.prompts import (
    JAMES_SYSTEM_PROMPT,
    JAMES_CLASSIFY_PROMPT,
    JAMES_SUMMARY_PROMPT,
    JAMES_EMAIL_PROMPT,
)
from graph.state import MaintenanceState
import services.llm_service as llm
from tools.db_tools import (
    get_todays_tickets,
    get_ticket_counts,
    get_tickets_by_status,
)

logger = logging.getLogger(__name__)


async def james_node(state: MaintenanceState, config: dict) -> dict:
    """
    Main James supervisor node.
    On first call: classifies intent and routes.
    On return from sub-agents: generates final summary.
    """
    messages = state.get("messages", [])
    current_agent = state.get("current_agent", "")
    iteration = state.get("iteration_count", 0)

    # Get the Chainlit streaming callback if available
    cl_callback = config.get("configurable", {}).get("cl_callback")
    agent_callback = config.get("configurable", {}).get("agent_callback")

    # Notify UI that James is active
    if agent_callback:
        await agent_callback("james", "thinking")

    # ---- RETURNING FROM SUB-AGENT: Generate summary ----
    if current_agent and current_agent != "james":
        return await _generate_summary(state, config)

    # ---- FIRST CALL: Classify intent and route ----
    last_human_msg = None
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            last_human_msg = msg.content
            break

    if not last_human_msg:
        return {
            "messages": [AIMessage(content="Hello! How can I help you with maintenance operations today?")],
            "current_agent": "james",
            "next_agent": "end",
            "iteration_count": iteration + 1,
        }

    # Classify user intent using lightweight model
    intent = await llm.classify(last_human_msg, INTENT_CATEGORIES)
    logger.info(f"James classified intent: {intent}")

    # Handle general Q&A directly
    if intent == "general_qa":
        return await _handle_general_qa(state, last_human_msg, config)

    # Handle ticket/priority queries - get data from DB first
    if intent in ("ticket_query", "priority_query"):
        return await _handle_ticket_query(state, last_human_msg, intent, config)

    # Route to appropriate agent for execution
    if intent in ("execute_maintenance", "execute_single_ticket"):
        # Get today's tickets for David
        tickets = await get_todays_tickets.ainvoke(
            {"due_date": date.today().isoformat()}
        )

        intro_msg = f"I've identified **{len(tickets)}** maintenance task(s) scheduled for today. "
        intro_msg += "Let me hand this over to **David** (Maintenance Supervisor) to create work orders and assign technicians."

        if cl_callback:
            for token in intro_msg:
                await cl_callback(token, "james")

        return {
            "messages": [AIMessage(content=intro_msg)],
            "current_agent": "james",
            "next_agent": "david",
            "user_intent": intent,
            "ticket_ids": [t["id"] for t in tickets] if tickets else [],
            "iteration_count": iteration + 1,
            "agent_outputs": [{"agent": "james", "content": intro_msg}],
        }

    if intent == "inventory_query":
        intro_msg = "Let me check with **Mira** (Inventory Manager) for you."

        if cl_callback:
            for token in intro_msg:
                await cl_callback(token, "james")

        return {
            "messages": [AIMessage(content=intro_msg)],
            "current_agent": "james",
            "next_agent": "mira",
            "user_intent": intent,
            "iteration_count": iteration + 1,
            "agent_outputs": [{"agent": "james", "content": intro_msg}],
        }

    if intent == "email_report":
        return {
            "messages": [AIMessage(content="I'll prepare a maintenance status report and send it to your email.")],
            "current_agent": "james",
            "next_agent": "email",
            "user_intent": intent,
            "iteration_count": iteration + 1,
        }

    # Fallback
    return await _handle_general_qa(state, last_human_msg, config)


async def _handle_general_qa(
    state: MaintenanceState, message: str, config: dict
) -> dict:
    """Handle general Q&A directly with GPT-4o."""
    cl_callback = config.get("configurable", {}).get("cl_callback")
    iteration = state.get("iteration_count", 0)

    messages = [
        {"role": "system", "content": JAMES_SYSTEM_PROMPT},
        {"role": "user", "content": message},
    ]

    # Stream the response
    response_text = ""
    async for token in await llm.chat(messages=messages, stream=True):
        response_text += token
        if cl_callback:
            await cl_callback(token, "james")

    return {
        "messages": [AIMessage(content=response_text)],
        "current_agent": "james",
        "next_agent": "end",
        "user_intent": "general_qa",
        "final_summary": response_text,
        "iteration_count": iteration + 1,
    }


async def _handle_ticket_query(
    state: MaintenanceState, message: str, intent: str, config: dict
) -> dict:
    """Handle ticket/priority queries by fetching data and responding."""
    cl_callback = config.get("configurable", {}).get("cl_callback")
    iteration = state.get("iteration_count", 0)

    # Fetch relevant data
    todays_tickets = await get_todays_tickets.ainvoke(
        {"due_date": date.today().isoformat()}
    )
    ticket_counts = await get_ticket_counts.ainvoke({})
    open_tickets = await get_tickets_by_status.ainvoke({"status": "open"})

    # Build context for the LLM
    data_context = (
        f"Today's date: {date.today().isoformat()}\n\n"
        f"Today's scheduled tickets ({len(todays_tickets)}):\n"
    )
    for t in todays_tickets:
        data_context += (
            f"- {t['ticket_number']} ({t['ticket_type']}) | {t['title']} | "
            f"Machine: {t['machine_name']} | Priority: {t['priority']} | "
            f"Status: {t['status']}\n"
        )

    data_context += f"\nOverall ticket counts: {ticket_counts}\n"
    data_context += f"\nAll open tickets ({len(open_tickets)}):\n"
    for t in open_tickets:
        data_context += (
            f"- {t['ticket_number']} ({t['ticket_type']}) | {t['title']} | "
            f"Machine: {t['machine_name']} | Priority: {t['priority']} | "
            f"Due: {t.get('due_date', 'N/A')}\n"
        )

    messages = [
        {"role": "system", "content": JAMES_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"User asked: {message}\n\n"
                f"Here is the current maintenance data from the database:\n\n"
                f"{data_context}\n\n"
                f"Provide a clear, well-formatted answer using markdown tables where appropriate."
            ),
        },
    ]

    response_text = ""
    async for token in await llm.chat(messages=messages, stream=True):
        response_text += token
        if cl_callback:
            await cl_callback(token, "james")

    return {
        "messages": [AIMessage(content=response_text)],
        "current_agent": "james",
        "next_agent": "end",
        "user_intent": intent,
        "final_summary": response_text,
        "iteration_count": iteration + 1,
    }


async def _generate_summary(state: MaintenanceState, config: dict) -> dict:
    """Generate a final summary from sub-agent work."""
    cl_callback = config.get("configurable", {}).get("cl_callback")
    iteration = state.get("iteration_count", 0)
    agent_outputs = state.get("agent_outputs", [])

    # Compile results from all agents
    results = ""
    for output in agent_outputs:
        results += f"\n--- {output.get('agent', 'Unknown').upper()} ---\n"
        results += output.get("content", "") + "\n"

    messages = [
        {"role": "system", "content": JAMES_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": JAMES_SUMMARY_PROMPT.format(results=results),
        },
    ]

    response_text = ""
    async for token in await llm.chat(
        messages=messages,
        model=MODELS["lightweight"],
        temperature=MODELS["temperature_creative"],
        stream=True,
    ):
        response_text += token
        if cl_callback:
            await cl_callback(token, "james")

    return {
        "messages": [AIMessage(content=response_text)],
        "current_agent": "james",
        "next_agent": "end",
        "final_summary": response_text,
        "iteration_count": iteration + 1,
    }


async def send_email_report(state: MaintenanceState, config: dict) -> dict:
    """Generate and send an email maintenance report."""
    import os
    from tools.email_tools import send_maintenance_report
    from tools.db_tools import get_todays_tickets, get_ticket_counts, get_low_stock_parts

    cl_callback = config.get("configurable", {}).get("cl_callback")
    iteration = state.get("iteration_count", 0)

    # Gather data
    tickets = await get_todays_tickets.ainvoke(
        {"due_date": date.today().isoformat()}
    )
    counts = await get_ticket_counts.ainvoke({})
    low_stock = await get_low_stock_parts.ainvoke({})

    report_data = (
        f"Date: {date.today().isoformat()}\n"
        f"Today's Tickets: {len(tickets)}\n"
        f"Ticket Counts: {counts}\n\n"
        f"Tickets:\n"
    )
    for t in tickets:
        report_data += f"- {t['ticket_number']}: {t['title']} ({t['priority']})\n"

    report_data += f"\nLow Stock Parts ({len(low_stock)}):\n"
    for p in low_stock:
        report_data += f"- {p['part_number']}: {p['part_name']} (stock: {p['quantity_on_hand']})\n"

    # Generate email via LLM
    email_response = await llm.chat(
        messages=[
            {"role": "system", "content": JAMES_SYSTEM_PROMPT},
            {"role": "user", "content": JAMES_EMAIL_PROMPT.format(report_data=report_data)},
        ],
        model=MODELS["lightweight"],
        stream=False,
    )

    email_content = email_response["content"]

    # Parse subject and body
    subject = "Maintenance Status Report"
    body = email_content
    if "SUBJECT:" in email_content:
        parts = email_content.split("BODY:", 1)
        subject = parts[0].replace("SUBJECT:", "").strip()
        body = parts[1].strip() if len(parts) > 1 else email_content

    # Send email
    recipient = os.getenv("USER_EMAIL", "")
    if recipient:
        result = await send_maintenance_report.ainvoke(
            {
                "recipient_email": recipient,
                "subject": subject,
                "report_body": body,
            }
        )
        status_msg = f"Email report sent to {recipient}."
    else:
        status_msg = "Email report generated but no recipient email configured."

    if cl_callback:
        for token in status_msg:
            await cl_callback(token, "james")

    return {
        "messages": [AIMessage(content=status_msg)],
        "current_agent": "james",
        "next_agent": "james",
        "email_report": body,
        "iteration_count": iteration + 1,
        "agent_outputs": (state.get("agent_outputs", []) or []) + [
            {"agent": "james", "content": f"Email Report:\n{status_msg}"}
        ],
    }
