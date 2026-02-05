"""
Agentic Maintenance Planning System - Chainlit Entry Point
============================================================
Main application file that bridges LangGraph orchestration with Chainlit UI.
Handles:
- Chat session initialization (graph, avatars, welcome message)
- User message routing into the LangGraph graph
- Streaming agent responses with per-agent avatars
- Human-in-the-loop (HITL) interrupt detection and resume
- Work order card display and technician action handling
"""

import logging
import uuid
from typing import Optional

import chainlit as cl
from langchain_core.messages import HumanMessage
from langgraph.types import Command, interrupt

from config.settings import AGENTS, UI
from graph.builder import compile_graph
from graph.state import MaintenanceState
from services.database import DatabaseService
from ui.avatars import register_all_avatars
from ui.cards import (
    display_work_order_card,
    display_technician_actions,
    get_technician_text_input,
)
from ui.streaming import StreamManager, create_stream_callback, create_agent_callback

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================
# Chat Lifecycle Hooks
# ============================================================


@cl.on_chat_start
async def on_chat_start():
    """Initialize a new chat session."""
    logger.info("New chat session starting...")

    # Initialize database connection pool
    await DatabaseService.initialize()

    # Compile the LangGraph graph with PostgreSQL checkpointer
    db_uri = DatabaseService.get_dsn()
    graph, checkpointer = await compile_graph(db_uri)

    # Generate unique thread ID for this session
    thread_id = str(uuid.uuid4())

    # Create streaming manager
    stream_manager = StreamManager()

    # Store in session
    cl.user_session.set("graph", graph)
    cl.user_session.set("checkpointer", checkpointer)
    cl.user_session.set("thread_id", thread_id)
    cl.user_session.set("stream_manager", stream_manager)
    cl.user_session.set("awaiting_hitl", False)
    cl.user_session.set("hitl_payload", None)

    # Register all agent avatars
    await register_all_avatars()

    # Send welcome message
    welcome = UI["welcome_message"]
    await cl.Message(
        content=welcome,
        author=AGENTS["james"]["name"],
    ).send()

    logger.info(f"Chat session initialized. Thread ID: {thread_id}")


@cl.on_chat_end
async def on_chat_end():
    """Clean up when chat session ends."""
    logger.info("Chat session ending...")
    # Database pool persists across sessions


# ============================================================
# Message Handler
# ============================================================


@cl.on_message
async def on_message(message: cl.Message):
    """Handle incoming user messages."""
    graph = cl.user_session.get("graph")
    thread_id = cl.user_session.get("thread_id")
    stream_manager: StreamManager = cl.user_session.get("stream_manager")
    awaiting_hitl = cl.user_session.get("awaiting_hitl", False)

    if not graph or not thread_id:
        await cl.Message(
            content="Session not initialized. Please refresh the page.",
            author=AGENTS["system"]["name"],
        ).send()
        return

    # Build LangGraph config with streaming callbacks
    config = {
        "configurable": {
            "thread_id": thread_id,
            "cl_callback": create_stream_callback(stream_manager),
            "agent_callback": create_agent_callback(stream_manager),
        }
    }

    try:
        # ---- CASE 1: Resuming from HITL interrupt ----
        if awaiting_hitl:
            await _handle_hitl_resume(message, graph, config, stream_manager)
            return

        # ---- CASE 2: Normal message processing ----
        await _handle_normal_message(message, graph, config, stream_manager)

    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
        await stream_manager.finalize()
        await cl.Message(
            content=f"An error occurred while processing your request. Please try again.\n\n*Error: {str(e)}*",
            author=AGENTS["system"]["name"],
        ).send()


# ============================================================
# Normal Message Flow
# ============================================================


async def _handle_normal_message(
    message: cl.Message,
    graph,
    config: dict,
    stream_manager: StreamManager,
):
    """Process a normal user message through the LangGraph graph."""
    thread_id = config["configurable"]["thread_id"]

    # Initial state for the graph
    input_state = {
        "messages": [HumanMessage(content=message.content)],
        "current_agent": "",
        "next_agent": None,
        "user_intent": None,
        "iteration_count": 0,
        "max_iterations": 15,
    }

    # Run the graph
    # We use stream mode to detect interrupts
    events = []
    final_state = None

    async for event in graph.astream(
        input_state,
        config=config,
        stream_mode="updates",
    ):
        events.append(event)
        # Each event is a dict of {node_name: state_update}
        for node_name, update in event.items():
            if node_name == "__interrupt__":
                # Graph hit an interrupt (technician HITL)
                await stream_manager.finalize()
                await _handle_hitl_interrupt(update, stream_manager)
                return

    # Finalize streaming
    await stream_manager.finalize()

    # Check final state for any remaining interrupt
    try:
        state = await graph.aget_state(config)
        if state and hasattr(state, 'tasks') and state.tasks:
            # There are pending interrupts
            for task in state.tasks:
                if hasattr(task, 'interrupts') and task.interrupts:
                    interrupt_value = task.interrupts[0].value
                    await _handle_hitl_interrupt(interrupt_value, stream_manager)
                    return
    except Exception as e:
        logger.debug(f"State check: {e}")


# ============================================================
# Human-in-the-Loop (HITL) Handling
# ============================================================


async def _handle_hitl_interrupt(
    interrupt_payload: dict,
    stream_manager: StreamManager,
):
    """
    Handle a graph interrupt (technician HITL).
    Display work order card and action buttons, then wait for user input.
    """
    logger.info(f"HITL interrupt detected: {interrupt_payload}")

    # Store the interrupt payload
    cl.user_session.set("awaiting_hitl", True)
    cl.user_session.set("hitl_payload", interrupt_payload)

    # Display the work order card
    if isinstance(interrupt_payload, dict):
        await display_work_order_card(interrupt_payload)
    elif isinstance(interrupt_payload, list) and interrupt_payload:
        await display_work_order_card(interrupt_payload[0])

    # Display action buttons
    action_result = await display_technician_actions()
    action = action_result.get("action", "add_notes")

    # If action requires additional input, get it
    if action == "request_parts":
        parts_text = await get_technician_text_input(
            "Which parts do you need? Describe them naturally "
            "(e.g., 'I need 2 bearings and a hydraulic filter'):"
        )
        resume_payload = {
            "action": "request_parts",
            "text": parts_text,
            "parts_requested": [p.strip() for p in parts_text.split(",") if p.strip()] if "," in parts_text else [parts_text],
        }
    elif action == "add_notes":
        notes_text = await get_technician_text_input(
            "Enter your notes or observations:"
        )
        resume_payload = {
            "action": "add_notes",
            "text": notes_text,
        }
    elif action == "reschedule":
        reason = await get_technician_text_input(
            "Why does this need to be rescheduled?"
        )
        resume_payload = {
            "action": "reschedule",
            "text": reason,
        }
    else:
        # confirm_completion
        resume_payload = {
            "action": "confirm_completion",
            "text": "Work completed successfully.",
        }

    # Store the resume payload and process it
    cl.user_session.set("hitl_resume_payload", resume_payload)

    # Auto-resume the graph with the action
    await _resume_graph_from_hitl(resume_payload, stream_manager)


async def _handle_hitl_resume(
    message: cl.Message,
    graph,
    config: dict,
    stream_manager: StreamManager,
):
    """
    Handle a message that comes in while awaiting HITL.
    The user typed something instead of using action buttons.
    """
    # Treat the message as free-text technician input
    resume_payload = {
        "action": "",  # Will be parsed by LLM in technician node
        "text": message.content,
        "parts_requested": [],
    }

    await _resume_graph_from_hitl(resume_payload, stream_manager)


async def _resume_graph_from_hitl(
    resume_payload: dict,
    stream_manager: StreamManager,
):
    """Resume the graph from a HITL interrupt with the technician's response."""
    graph = cl.user_session.get("graph")
    thread_id = cl.user_session.get("thread_id")

    config = {
        "configurable": {
            "thread_id": thread_id,
            "cl_callback": create_stream_callback(stream_manager),
            "agent_callback": create_agent_callback(stream_manager),
        }
    }

    # Clear HITL state
    cl.user_session.set("awaiting_hitl", False)
    cl.user_session.set("hitl_payload", None)

    try:
        # Resume the graph with the technician's response
        async for event in graph.astream(
            Command(resume=resume_payload),
            config=config,
            stream_mode="updates",
        ):
            # Check for nested interrupts (technician asked for parts -> mira -> back to tech)
            for node_name, update in event.items():
                if node_name == "__interrupt__":
                    await stream_manager.finalize()
                    await _handle_hitl_interrupt(update, stream_manager)
                    return

        await stream_manager.finalize()

        # Check for pending interrupts in final state
        try:
            state = await graph.aget_state(config)
            if state and hasattr(state, 'tasks') and state.tasks:
                for task in state.tasks:
                    if hasattr(task, 'interrupts') and task.interrupts:
                        interrupt_value = task.interrupts[0].value
                        await _handle_hitl_interrupt(interrupt_value, stream_manager)
                        return
        except Exception as e:
            logger.debug(f"State check after resume: {e}")

    except Exception as e:
        logger.error(f"Error resuming from HITL: {e}", exc_info=True)
        await stream_manager.finalize()
        await cl.Message(
            content=f"Error resuming workflow: {str(e)}",
            author=AGENTS["system"]["name"],
        ).send()


# ============================================================
# Action Callback (for cl.Action buttons)
# ============================================================


@cl.action_callback("confirm_completion")
async def on_confirm_completion(action: cl.Action):
    """Handle the 'Work Completed' action button."""
    await action.remove()
    cl.user_session.set("hitl_resume_payload", {
        "action": "confirm_completion",
        "text": "Work completed successfully.",
    })


@cl.action_callback("request_parts")
async def on_request_parts(action: cl.Action):
    """Handle the 'Request Parts' action button."""
    await action.remove()


@cl.action_callback("reschedule")
async def on_reschedule(action: cl.Action):
    """Handle the 'Reschedule' action button."""
    await action.remove()


@cl.action_callback("add_notes")
async def on_add_notes(action: cl.Action):
    """Handle the 'Add Notes' action button."""
    await action.remove()
