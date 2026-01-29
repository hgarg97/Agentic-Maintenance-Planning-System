from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from orchestration.state import MaintenanceState
from orchestration.prompts import (
    OPERATOR_AGENT_PROMPT,
    SUPERVISOR_AGENT_PROMPT,
    TECHNICIAN_AGENT_PROMPT,
    INVENTORY_AGENT_PROMPT,
    PRE_APPROVAL_SUMMARY_PROMPT,  # James gives recommendation
    SUMMARY_AGENT_PROMPT,
)
from orchestration.agent_executor import AgentOrchestrator
from orchestration.error_handler import (
    safe_agent_execution,
    with_retry,
    can_proceed_with_degradation,
    get_degraded_response
)
from config.personas import get_technician_persona
import sys
import json
from datetime import datetime

def log_state_to_terminal(agent_name: str, state: dict):
    """
    Log important state information to terminal for debugging.
    """
    colors = {
        "INFO": "\033[94m",
        "SUCCESS": "\033[92m",
        "AGENT": "\033[95m",
        "RESET": "\033[0m"
    }
    
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    
    print(f"\n{colors['AGENT']}╔═══════════════════════════════════════════════════════════╗{colors['RESET']}", file=sys.stderr)
    print(f"{colors['AGENT']}║  [{timestamp}] {agent_name.upper():^45} ║{colors['RESET']}", file=sys.stderr)
    print(f"{colors['AGENT']}╠═══════════════════════════════════════════════════════════╣{colors['RESET']}", file=sys.stderr)
    
    # Key state fields to log
    important_fields = {
        "intent": state.get("intent"),
        "work_order_id": state.get("work_order", {}).get("work_order_id"),
        "required_parts_count": len(state.get("required_parts", [])),
        "can_execute": state.get("can_execute"),
        "purchase_required": state.get("purchase_required"),
        "next_agent": state.get("next_agent"),
        "current_step": state.get("current_step"),
        "tool_calls_count": len(state.get("tool_calls", [])),
        "errors_count": len(state.get("errors", [])),
    }
    
    for key, value in important_fields.items():
        if value is not None:
            print(f"{colors['INFO']}║  {key:20s}: {str(value):36s} ║{colors['RESET']}", file=sys.stderr)
    
    print(f"{colors['AGENT']}╚═══════════════════════════════════════════════════════════╝{colors['RESET']}\n", file=sys.stderr)

# =========================
# Global orchestrator
# =========================

orchestrator = AgentOrchestrator()

# Register role-based agents
orchestrator.register_agent("operator_agent", OPERATOR_AGENT_PROMPT, max_iterations=3)
orchestrator.register_agent("supervisor_agent", SUPERVISOR_AGENT_PROMPT, max_iterations=4)
orchestrator.register_agent("technician_agent", TECHNICIAN_AGENT_PROMPT, max_iterations=5)
orchestrator.register_agent("inventory_agent", INVENTORY_AGENT_PROMPT, max_iterations=4)
orchestrator.register_agent("pre_approval_summary", PRE_APPROVAL_SUMMARY_PROMPT, max_iterations=3)  # James gives recommendation
orchestrator.register_agent("summary_agent", SUMMARY_AGENT_PROMPT, max_iterations=2)


# =========================
# Agent execution helpers
# =========================

def should_skip_agent(state: MaintenanceState, agent_name: str) -> bool:
    """Determine if an agent should be skipped based on state"""
    
    # Check skip flags
    skip_flags = {
        "planning_agent": state.get("skip_planning", False),
        "inventory_agent": state.get("skip_inventory", False),
        "reservation_agent": state.get("skip_reservation", False),
        "purchase_agent": state.get("skip_purchase", False),
    }
    
    if skip_flags.get(agent_name, False):
        return True
    
    # Smart skipping based on intent
    intent = state.get("intent", "")
    
    # For simple queries, skip planning if not needed
    if agent_name == "planning_agent" and intent in {"list_work_orders"}:
        return True
    
    # Skip inventory check if no parts required
    if agent_name == "inventory_agent":
        if not state.get("required_parts"):
            return True
    
    # Skip reservation if it's a read-only intent
    if agent_name == "reservation_agent":
        read_only = intent in {"material_readiness", "blockage_reason", "list_work_orders"}
        if read_only:
            # Still need to assess, but won't actually reserve
            return False
    
    # Skip purchase if no purchase is required
    if agent_name == "purchase_agent":
        if not state.get("purchase_required", False):
            return True
    
    return False


def execute_agent_with_fallback(
    agent_name: str,
    state: MaintenanceState,
    task: str,
    context: dict,
    available_data: dict = None
) -> MaintenanceState:
    """Execute agent with error handling and fallback"""
    
    try:
        response = orchestrator.execute_agent(
            agent_name,
            task=task,
            context=context,
            available_data=available_data
        )
        
        # Track execution
        if "execution_path" not in state:
            state["execution_path"] = []
        state["execution_path"].append(agent_name)
        
        # Track tool usage
        if "tool_calls" not in state:
            state["tool_calls"] = []
        state["tool_calls"].extend(response.tool_calls_made)
        
        # Track totals
        state["total_tool_calls"] = len(state["tool_calls"])
        
        return response, True
    
    except Exception as e:
        # Log error but continue
        if "errors" not in state:
            state["errors"] = []
        
        state["errors"].append({
            "agent": agent_name,
            "error": str(e),
            "recoverable": True
        })
        
        return None, False


# =========================
# Agent nodes - Role-Based Maintenance System
# =========================

@safe_agent_execution
def operator_agent(state: MaintenanceState) -> MaintenanceState:
    """Sarah - Equipment Operator - Identifies issues"""
    
    work_order = state.get("work_order", {})
    work_order_id = work_order.get("work_order_id", "")
    
    task = f"Review work order {work_order_id} and identify any equipment issues that need attention."
    
    context = {
        "work_order_id": work_order_id,
        "equipment": work_order.get("equipment_name", ""),
        "wo_type": work_order.get("wo_type", ""),
    }
    
    available_data = {"work_order": work_order} if work_order else None
    
    response, success = execute_agent_with_fallback(
        "operator_agent", state, task, context, available_data
    )
    
    if success and response.final_state:
        state["issue_identified"] = response.final_state.get("issue_identified", True)
        state["issue_description"] = response.final_state.get("issue_description", "")
        state["severity"] = response.final_state.get("severity", "Medium")
    
    state["current_step"] = "issue_detection"
    log_state_to_terminal("operator_agent", state)
    return state


@safe_agent_execution
def supervisor_agent(state: MaintenanceState) -> MaintenanceState:
    """David - Maintenance Supervisor - Creates WO and assigns to technician"""
    
    work_order = state.get("work_order", {})
    work_order_id = work_order.get("work_order_id", "")
    primary_role = work_order.get("primary_role", "MMT")
    
    task = (
        f"Review work order {work_order_id} and assign it to the appropriate technician. "
        f"The work order is currently assigned to {primary_role}."
    )
    
    context = {
        "work_order_id": work_order_id,
        "equipment": work_order.get("equipment_name", ""),
        "description": work_order.get("description", ""),
        "current_assignment": primary_role,
    }
    
    available_data = {"work_order": work_order} if work_order else None
    
    response, success = execute_agent_with_fallback(
        "supervisor_agent", state, task, context, available_data
    )
    
    if success and response.final_state:
        assigned_role = response.final_state.get("assigned_to", primary_role)
        state["assigned_technician"] = assigned_role
        state["requires_lockout"] = response.final_state.get("requires_lockout", False)
        state["safety_critical"] = response.final_state.get("safety_critical", False)
        
        # Map role to technician name
        role_to_name = {"MMT": "Mike", "EMT": "Eric", "HT": "Henry"}
        state["technician_name"] = role_to_name.get(assigned_role, "Mike")
    else:
        # Fallback to primary role from WO
        state["assigned_technician"] = primary_role
        state["technician_name"] = {"MMT": "Mike", "EMT": "Eric", "HT": "Henry"}.get(primary_role, "Mike")
    
    state["current_step"] = "work_assignment"
    log_state_to_terminal("supervisor_agent", state)
    return state


@safe_agent_execution  
def technician_agent(state: MaintenanceState) -> MaintenanceState:
    """Mike/Eric/Henry - Dynamic Technician - Plans and executes work"""
    
    work_order = state.get("work_order", {})
    work_order_id = work_order.get("work_order_id", "")
    assigned_role = state.get("assigned_technician", "MMT")
    
    # Get technician persona based on assignment
    tech_persona = get_technician_persona(assigned_role)
    
    task = (
        f"You are {tech_persona['persona_name']} ({assigned_role}). "
        f"Review work order {work_order_id} and plan your work. "
        f"Identify what spare parts you need."
    )
    
    context = {
        "work_order_id": work_order_id,
        "your_role": assigned_role,
        "your_name": tech_persona['persona_name'],
        "equipment": work_order.get("equipment_name", ""),
    }
    
    available_data = {
        "work_order": work_order,
        "technician_persona": tech_persona
    }
    
    response, success = execute_agent_with_fallback(
        "technician_agent", state, task, context, available_data
    )
    
    if success:
        # Extract required parts from tool calls
        for tool_call in response.tool_calls_made:
            if tool_call["tool_name"] == "get_required_parts_for_work_order" and tool_call["success"]:
                state["required_parts"] = tool_call["result"]
        
        # Store technician context
        if response.final_state:
            state["technician_context"] = {
                "tasks_planned": response.final_state.get("tasks_planned", []),
                "parts_requested": response.final_state.get("parts_requested", []),
                "estimated_time": response.final_state.get("estimated_time", ""),
            }
    
    state["current_step"] = "work_planning"
    log_state_to_terminal("technician_agent", state)
    return state


@safe_agent_execution
def inventory_agent(state: MaintenanceState) -> MaintenanceState:
    """Mira - Storekeeper - Checks inventory and issues spares"""
    
    if should_skip_agent(state, "inventory_agent"):
        state["skip_inventory"] = True
        state["messages"].append("No spare parts needed")
        return state
    
    work_order_id = state["work_order"].get("work_order_id", "")
    
    task = (
        f"Check spare parts availability for work order {work_order_id}. "
        f"Issue parts if available, create purchase requisitions if not."
    )
    
    context = {
        "work_order_id": work_order_id,
        "technician": state.get("technician_name", "Technician"),
    }
    
    available_data = {}
    if state.get("required_parts"):
        available_data["required_parts"] = state["required_parts"]
    
    response, success = execute_agent_with_fallback(
        "inventory_agent", state, task, context, available_data
    )
    
    if success:
        # Extract inventory check results
        for tool_call in response.tool_calls_made:
            if tool_call["tool_name"] == "check_inventory_for_parts" and tool_call["success"]:
                state["inventory_status"] = tool_call["result"]
            elif tool_call["tool_name"] == "issue_spares_to_work_order" and tool_call["success"]:
                state["reservation_status"] = tool_call["result"]
            elif tool_call["tool_name"] == "create_purchase_requisitions" and tool_call["success"]:
                state["purchase_requests"] = tool_call["result"]
        
        # Check if purchase is required
        reservation_status = state.get("reservation_status", {})
        purchase_required = any(
            record.get("status") == "Not Available"
            for record in reservation_status.values()
        )
        state["purchase_required"] = purchase_required
        state["can_execute"] = not purchase_required
        
        # FIXED: Calculate inventory_context from actual tool results, not LLM response
        if reservation_status:
            issued_count = sum(1 for r in reservation_status.values() if r.get("status") == "Issued")
            unavailable_count = sum(1 for r in reservation_status.values() if r.get("status") == "Not Available")
            
            state["inventory_context"] = {
                "spares_checked": len(state.get("required_parts", [])),
                "spares_available": issued_count,
                "spares_issued": issued_count,
                "shortages": [p for p, r in reservation_status.items() if r.get("status") == "Not Available"],
                "issue_records": [
                    {
                        "issue_id": r.get("issue_id"),
                        "part_code": p,
                        "quantity": r.get("quantity_issued", 0)
                    }
                    for p, r in reservation_status.items() if r.get("status") == "Issued"
                ],
                "reorder_alerts": response.final_state.get("reorder_alerts", []) if response.final_state else []
            }
        elif response.final_state:
            # Fallback to LLM output if no tools were called
            state["inventory_context"] = {
                "spares_checked": response.final_state.get("spares_checked", 0),
                "spares_available": response.final_state.get("spares_available", 0),
                "spares_issued": response.final_state.get("spares_issued", 0),
                "shortages": response.final_state.get("shortages", []),
            }
    
    # Force execution if agent didn't call ALL necessary tools
    # CRITICAL: LLM might call check_inventory but forget issue_spares - we MUST ensure both happen
    if state.get("required_parts"):
        from csv_helper import check_inventory_for_parts, issue_spares_to_work_order, create_purchase_requisitions
        
        # Step 1: Ensure inventory was checked
        if not state.get("inventory_status"):
            print("⚠️  Forcing inventory check (LLM didn't call it)", file=sys.stderr)
            inventory_status = check_inventory_for_parts(state["required_parts"])
            state["inventory_status"] = inventory_status
        else:
            inventory_status = state["inventory_status"]
        
        # Step 2: CRITICAL - Always issue spares (LLM often forgets this)
        if not state.get("reservation_status"):
            print("⚠️  Forcing spare issue (LLM didn't call it)", file=sys.stderr)
            reservation_status = issue_spares_to_work_order(
                work_order_id,
                state["required_parts"],
                inventory_status
            )
            state["reservation_status"] = reservation_status
        else:
            reservation_status = state["reservation_status"]
        
        # Step 3: Create PRs if needed
        purchase_required = any(r.get("status") == "Not Available" for r in reservation_status.values())
        
        if purchase_required and not state.get("purchase_requests"):
            print("⚠️  Forcing purchase requisition creation (LLM didn't call it)", file=sys.stderr)
            purchase_requests = create_purchase_requisitions(
                work_order_id,
                reservation_status,
                state["required_parts"]
            )
            state["purchase_requests"] = purchase_requests
        
        state["purchase_required"] = purchase_required
        state["can_execute"] = not purchase_required
        
        # IMPORTANT: Set inventory_context for UI display
        issued_count = sum(1 for r in reservation_status.values() if r.get("status") == "Issued")
        unavailable_count = sum(1 for r in reservation_status.values() if r.get("status") == "Not Available")
        
        state["inventory_context"] = {
            "spares_checked": len(state["required_parts"]),
            "spares_available": issued_count,
            "spares_issued": issued_count,
            "shortages": [p for p, r in reservation_status.items() if r.get("status") == "Not Available"],
            "issue_records": [
                {
                    "issue_id": r.get("issue_id"),
                    "part_code": p,
                    "quantity": r.get("quantity_issued", 0)
                }
                for p, r in reservation_status.items() if r.get("status") == "Issued"
            ]
        }
    
    state["current_step"] = "parts_management"
    log_state_to_terminal("inventory_agent", state)
    return state


@safe_agent_execution
def pre_approval_summary(state: MaintenanceState) -> MaintenanceState:
    """James - Provides recommendation before human approval"""
    
    work_order_id = state["work_order"].get("work_order_id", "")
    
    # Determine recommendation based on state
    if state.get("purchase_required", False):
        recommendation = "PUT ON HOLD"
        reason = "Required parts are not available in inventory. Work cannot proceed until procurement is complete."
    else:
        recommendation = "APPROVE"
        reason = "All parts are available and work has been completed successfully by the technician."
    
    task = (
        f"Provide a concise summary and recommendation for work order {work_order_id}. "
        f"Your recommendation is: {recommendation}. "
        f"Reason: {reason}"
    )
    
    context = {
        "work_order_id": work_order_id,
        "technician": state.get("technician_name", ""),
        "parts_available": not state.get("purchase_required", False),
        "work_completed": True,
    }
    
    available_data = {
        "required_parts": state.get("required_parts", []),
        "inventory_status": state.get("inventory_status", {}),
        "reservation_status": state.get("reservation_status", {}),
        "purchase_requests": state.get("purchase_requests", []),
    }
    
    response, success = execute_agent_with_fallback(
        "pre_approval_summary", state, task, context, available_data
    )
    
    # Store recommendation in state
    state["human_approval_context"] = {
        "recommendation": recommendation,
        "recommendation_reason": reason,
        "awaiting_approval": True,
        "human_decision": "",
        "human_notes": "",
        "decision_timestamp": ""
    }
    
    # Store James's summary for display
    if success and response and response.content:
        state["messages"].append(f"James Recommendation: {response.content}")
    
    state["current_step"] = "awaiting_human_approval"
    log_state_to_terminal("pre_approval_summary", state)
    return state


def human_approval(state: MaintenanceState) -> MaintenanceState:
    """Human decision point - handled by UI, this node just validates"""
    
    approval_context = state.get("human_approval_context", {})
    human_decision = approval_context.get("human_decision", "")
    
    if human_decision == "APPROVED":
        state["work_completed"] = True
        state["verification_passed"] = True
        state["wo_closed"] = True
    elif human_decision == "ON_HOLD":
        state["work_completed"] = False
        state["verification_passed"] = False
        state["wo_closed"] = False
    
    state["current_step"] = "human_decision_recorded"
    log_state_to_terminal("human_approval", state)
    return state


@safe_agent_execution
def summary_agent(state: MaintenanceState) -> MaintenanceState:
    """James - System Coordinator - Presents complete journey"""
    
    work_order_id = state["work_order"].get("work_order_id", "")
    
    # Determine work order status for LLM context
    if state.get("purchase_required", False):
        status_description = "Work order is ON HOLD - awaiting procurement of unavailable parts"
    elif state.get("wo_closed", False):
        status_description = "Work order completed and closed successfully"
    else:
        status_description = "Work order in progress"
    
    task = (
        f"Present the complete work order journey for {work_order_id}. "
        f"IMPORTANT: {status_description}. "
        f"Show what each agent did and the final outcome. "
        f"If work is ON HOLD, clearly explain why and what's needed to proceed."
    )
    
    context = {
        "work_order_id": work_order_id,
        "final_status": status_description,
    }
    
    available_data = {
        "operator_findings": state.get("issue_description"),
        "supervisor_assignment": state.get("technician_name"),
        "technician_role": state.get("assigned_technician"),
        "required_parts": state.get("required_parts", []),
        "inventory_status": state.get("inventory_status", {}),
        "reservation_status": state.get("reservation_status", {}),
        "purchase_requests": state.get("purchase_requests", []),
        "work_completed": state.get("work_completed", False),
        "wo_closed": state.get("wo_closed", False),
        "purchase_required": state.get("purchase_required", False),
        "execution_path": state.get("execution_path", []),
    }
    
    response, success = execute_agent_with_fallback(
        "summary_agent", state, task, context, available_data
    )
    
    if success and response and response.content:
        state["final_answer"] = response.content
    else:
        # Fallback summary with clearer ON HOLD messaging
        summary_parts = [f"## Work Order {work_order_id} Summary\\n"]
        
        if state.get("technician_name"):
            summary_parts.append(f"**Assigned to:** {state['technician_name']} ({state.get('assigned_technician')})")
        
        if state.get("required_parts"):
            summary_parts.append(f"**Parts Required:** {len(state['required_parts'])}")
        
        if state.get("reservation_status"):
            issued = sum(1 for r in state["reservation_status"].values() if r.get("status") == "Issued")
            summary_parts.append(f"**Parts Issued:** {issued}")
        
        if state.get("purchase_requests"):
            summary_parts.append(f"**Purchase Requisitions Created:** {len(state['purchase_requests'])}")
            
            # List the PRs
            summary_parts.append("\\n**Missing Parts:**")
            for pr in state.get("purchase_requests", []):
                part_code = pr.get("part_code", "Unknown")
                qty = pr.get("requested_qty", 0)
                pr_id = pr.get("pr_id", "Unknown")
                summary_parts.append(f"  - {part_code} (Qty: {int(qty)}) - PR: {pr_id}")
        
        # Status determination with clear messaging
        if state.get("purchase_required"):
            summary_parts.append("\\n---")
            summary_parts.append("\\n## ON HOLD - Work Order Status")
            summary_parts.append("\\nThis work order cannot proceed until the required spare parts are received from procurement.")
            summary_parts.append("\\n**Next Steps:**")
            summary_parts.append("1. Wait for purchase requisitions to be fulfilled")
            summary_parts.append("2. Once parts arrive, Mira will update inventory")
            summary_parts.append("3. Work can then be scheduled and completed")
        elif state.get("wo_closed"):
            summary_parts.append("\\n---")
            summary_parts.append("\\n## CLOSED - Work Order Status")
            summary_parts.append("\\nAll work completed successfully and verified by safety officer.")
        else:
            summary_parts.append("\\n---")
            summary_parts.append("\\n## IN PROGRESS - Work Order Status")
        
        state["final_answer"] = "\\n".join(summary_parts)
    
    state["current_step"] = "completed"
    log_state_to_terminal("summary_agent", state)
    return state


# =========================
# Dynamic routing functions  
# =========================

def route_from_operator(state: MaintenanceState) -> str:
    """After operator identifies issue, go to supervisor"""
    return "supervisor_agent"


def route_from_supervisor(state: MaintenanceState) -> str:
    """After supervisor assigns work, go to technician"""
    return "technician_agent"


def route_from_technician(state: MaintenanceState) -> str:
    """After technician plans work, go to inventory"""
    # Skip inventory if no parts required
    if not state.get("required_parts"):
        return "pre_approval_summary"
    return "inventory_agent"


def route_from_inventory(state: MaintenanceState) -> str:
    """After inventory check, go to James for recommendation"""
    return "pre_approval_summary"


def route_from_pre_approval(state: MaintenanceState) -> str:
    """After James's recommendation, wait for human approval"""
    return "human_approval"


def route_from_human_approval(state: MaintenanceState) -> str:
    """After human decision, go to final summary"""
    return "summary_agent"


# =========================
# Graph builder
# =========================

def build_graph():
    """Build the role-based maintenance graph with human approval"""
    graph = StateGraph(MaintenanceState)

    # Add nodes
    graph.add_node("operator_agent", operator_agent)
    graph.add_node("supervisor_agent", supervisor_agent)
    graph.add_node("technician_agent", technician_agent)
    graph.add_node("inventory_agent", inventory_agent)
    graph.add_node("pre_approval_summary", pre_approval_summary)  # James gives recommendation
    graph.add_node("human_approval", human_approval)  # Human makes decision
    graph.add_node("summary_agent", summary_agent)  # Final summary

    # Set entry point
    graph.set_entry_point("operator_agent")

    # Linear flow with human approval
    graph.add_edge("operator_agent", "supervisor_agent")
    graph.add_edge("supervisor_agent", "technician_agent")
    
    graph.add_conditional_edges(
        "technician_agent",
        route_from_technician,
        {
            "inventory_agent": "inventory_agent",
            "pre_approval_summary": "pre_approval_summary",  # Skip inventory if no parts
        },
    )
    
    # After inventory, always go to James for recommendation
    graph.add_edge("inventory_agent", "pre_approval_summary")
    
    # After James's recommendation, go to human approval
    graph.add_edge("pre_approval_summary", "human_approval")
    
    # After human decision, show final summary
    graph.add_edge("human_approval", "summary_agent")
    graph.add_edge("summary_agent", END)

    # CRITICAL: Use LangGraph's interrupt_before for human-in-the-loop
    # This will pause execution BEFORE human_approval node
    memory = MemorySaver()
    return graph.compile(
        interrupt_before=["human_approval"],
        checkpointer=memory
    )