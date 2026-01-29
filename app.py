# app.py - HUMANIZED ROLE-BASED MAINTENANCE SYSTEM WITH HUMAN-IN-THE-LOOP APPROVAL
"""
Beautiful UI for maintenance planning system with HUMAN-LIKE conversations and human approval.
Agents: Sarah (Operator), David (Supervisor), Mike/Eric/Henry (Technician),
        Mira (Inventory), James (Pre-Approval + Summary)
        
Human Decision: CEO/Manager approves or puts work orders ON HOLD
        
This version makes agents sound like real maintenance workers having natural conversations,
with a final human decision step for real engagement.
"""

import chainlit as cl
from typing import List, Dict
import asyncio
import sys
import re
import random
from datetime import datetime
from orchestration.state import MaintenanceState
from orchestration.graph import build_graph
from csv_helper import get_work_order_by_id, get_all_work_orders
from config.personas import PERSONAS, get_technician_persona
from langchain_openai import ChatOpenAI
from orchestration.query_parser import handle_data_query

# Build graph once
graph = build_graph()

# LLM for optional streaming responses
def _llm():
    return ChatOpenAI(model="gpt-4o-mini", temperature=0.3, streaming=True)


# =========================
# Humanized Response Templates
# =========================

SARAH_GREETINGS = [
    "Hey team, just finished my morning rounds.",
    "Morning everyone! Did my usual equipment check.",
    "Hi all, completed the shift inspection.",
    "Hey, checked the equipment during my rounds today.",
]

SARAH_CONCERNS = {
    "high": [
        "Guys, we've got a problem here.",
        "Team, this needs attention ASAP.",
        "This doesn't look good at all.",
        "We need to deal with this right away.",
    ],
    "medium": [
        "Found something that needs a look.",
        "There's an issue we should handle soon.",
        "Noticed something off today.",
        "We should probably check this out.",
    ],
    "low": [
        "Just a heads up about something minor.",
        "Spotted a small thing to keep an eye on.",
        "Nothing urgent, but wanted to mention this.",
        "Small issue, but thought you should know.",
    ]
}

DAVID_ACKNOWLEDGMENTS = [
    "Got it, Sarah. Let me take a look at this.",
    "Thanks for the heads up. I'll handle this.",
    "Alright, I see what we're dealing with here.",
    "Okay, reviewing this now.",
]

DAVID_ASSIGNMENTS = {
    "MMT": [
        "This is definitely Mike's area - mechanical work.",
        "Mike, this one's got your name on it. Mechanical issue.",
        "Assigning this to Mike - right up his alley.",
        "Mike should handle this. It's a mechanical job.",
    ],
    "EMT": [
        "Eric, you're up. This is electrical.",
        "This needs Eric's touch - electrical system.",
        "Assigning to Eric. Electrical expertise needed here.",
        "Eric, this is your specialty. Electrical work.",
    ],
    "HT": [
        "Henry, I need you on this. Hydraulics.",
        "This is hydraulic - Henry's the guy for this.",
        "Henry, you're the best for this hydraulic issue.",
        "Assigning to Henry. Hydraulic system work.",
    ]
}

TECH_ACKNOWLEDGMENTS = {
    "confident": [
        "Yeah, I can handle this. No problem.",
        "Got it. I've done this plenty of times.",
        "Sure thing. Pretty straightforward.",
        "Alright, I know exactly what to do.",
    ],
    "cautious": [
        "Okay, let me check what I need for this.",
        "Alright, I'll need to plan this out carefully.",
        "Got it. Let me make sure I have everything.",
        "This'll need some prep, but I'm on it.",
    ]
}

MIRA_GREETINGS = [
    "Hey! Let me check the inventory for you.",
    "Sure, pulling up the stock levels now.",
    "Alright, let's see what we have in stock.",
    "No problem, checking the parts right now.",
]

MIRA_GOOD_NEWS = [
    "Good news - we've got everything!",
    "You're in luck, all parts are in stock.",
    "Perfect timing - everything's available.",
    "We're all set, parts are ready to go.",
]

MIRA_BAD_NEWS = [
    "Ugh, we're short on some parts.",
    "Hmm, looks like we're running low on a couple items.",
    "Bad news - we don't have enough stock for everything.",
    "We've got a shortage here, unfortunately.",
]

JAMES_GREETINGS = [
    "Alright, let me recap what just happened here.",
    "Okay everyone, here's how this all went down.",
    "Let me summarize this whole work order for you.",
    "Here's the complete picture of what we did today.",
]


# =========================
# Terminal Logging
# =========================

def log_to_terminal(message: str, level: str = "INFO"):
    """Print colored logs to terminal for monitoring"""
    colors = {
        "INFO": "\033[94m",      # Blue
        "SUCCESS": "\033[92m",   # Green
        "WARNING": "\033[93m",   # Yellow
        "ERROR": "\033[91m",     # Red
        "AGENT": "\033[95m",     # Magenta
        "TOOL": "\033[96m",      # Cyan
        "RESET": "\033[0m"
    }
    
    color = colors.get(level, colors["INFO"])
    reset = colors["RESET"]
    timestamp = cl.context.session.id[:8] if hasattr(cl.context, 'session') else "system"
    
    print(f"{color}[{level}][{timestamp}] {message}{reset}", file=sys.stderr)


# =========================
# Helper functions
# =========================

def initialize_state(user_query: str, work_order_id: str) -> MaintenanceState:
    """Initialize state for a work order"""
    log_to_terminal(f"Initializing state for WO: {work_order_id}", "INFO")
    work_order = get_work_order_by_id(work_order_id)
    
    log_to_terminal(f"Work Order: {work_order.get('equipment_name', 'Unknown')} ({work_order.get('wo_type', 'Unknown')})", "SUCCESS")

    return MaintenanceState(
        user_query=user_query,
        work_order=work_order,
        intent="maintenance_planning",
        next_agent=None,
        
        # Role-based fields
        issue_identified=False,
        issue_description="",
        severity="",
        assigned_technician="",
        technician_name="",
        requires_lockout=False,
        safety_critical=False,
        work_started=False,
        work_completed=False,
        verification_passed=False,
        wo_closed=False,
        
        # Shared data
        required_parts=[],
        inventory_status={},
        reservation_status={},
        purchase_requests=[],
        
        # Flags
        can_execute=False,
        purchase_required=False,
        skip_planning=False,
        skip_inventory=False,
        skip_reservation=False,
        skip_purchase=False,
        
        # Contexts
        operator_context=None,
        supervisor_context=None,
        technician_context=None,
        inventory_context=None,
        safety_context=None,
        routing_context=None,
        planning_context=None,
        reservation_context=None,
        purchase_context=None,
        plan=None,
        
        # Tracking
        current_step="start",
        execution_path=[],
        tool_calls=[],
        errors=[],
        has_critical_error=False,
        retry_count=0,
        messages=[],
        final_answer=None,
        total_tool_calls=0,
        total_llm_calls=0,
    )


def render_persona_message(agent_role: str, content: str):
    """Render a message from an agent persona"""
    persona = PERSONAS.get(agent_role, {})
    return cl.Message(
        author=persona.get("persona_name", "System"),
        content=content,
    )


def _material_readiness_table(required_parts, inventory_status) -> str:
    """Generate material readiness table"""
    if not required_parts:
        return "No spare parts required for this work order."

    rows = []
    for p in required_parts:
        part_code = str(p.get("part_code") or p.get("part_id", ""))
        req = float(p.get("required_quantity", 0) or 0)
        inv = float(inventory_status.get(part_code, {}).get("available_quantity", 0) or 0)
        loc = inventory_status.get(part_code, {}).get("location")
        status = "✅" if inv >= req and req > 0 else "❌"
        loc_txt = loc if loc else "N/A"
        rows.append((part_code, req, inv, loc_txt, status))

    header = "| Part Code | Required | Available | Location | Status |\n|---------|----------|-----------|----------|:------:|"
    body = "\n".join([f"| {pc} | {req:g} | {inv:g} | {loc} | {st} |" for pc, req, inv, loc, st in rows])
    return header + "\n" + body


async def show_agent_thinking(agent_name: str, thinking: str):
    """Display agent's thinking process in a collapsible section"""
    persona = PERSONAS.get(agent_name, {})
    
    # Clean up the thinking text
    thinking_lines = thinking.strip().split('\n')
    formatted_thinking = '\n'.join([line.rstrip() for line in thinking_lines])
    
    thinking_content = f"""
<details>
<summary><b>💭 {persona.get('persona_name', 'Agent')}'s Thinking Process</b></summary>

```
{formatted_thinking}
```

</details>
"""
    
    log_to_terminal(f"{agent_name} thinking: {thinking[:100]}...", "AGENT")
    
    await cl.Message(
        author=persona.get("persona_name", "Agent"),
        content=thinking_content
    ).send()


async def show_tool_usage(agent_name: str, tool_calls: List[Dict]):
    """Display tools used by agent"""
    if not tool_calls:
        return
    
    persona = PERSONAS.get(agent_name, {})
    
    tool_lines = [f"### 🔧 **Tools Used**\n"]
    
    for idx, tool_call in enumerate(tool_calls, 1):
        tool_name = tool_call.get("tool_name", "unknown")
        success = tool_call.get("success", False)
        status_icon = "✅" if success else "❌"
        
        tool_display = tool_name.replace("_", " ").title()
        tool_lines.append(f"{status_icon} **{idx}. {tool_display}**")
        
        args = tool_call.get("args", {})
        if args:
            key_args = {k: v for k, v in args.items() if k in ["work_order_id", "part_code", "wo_type"]}
            if key_args:
                args_str = ", ".join([f"{k}={v}" for k, v in key_args.items()])
                tool_lines.append(f"   └─ *{args_str}*")
        
        log_to_terminal(f"{agent_name} used tool: {tool_name} [{'SUCCESS' if success else 'FAILED'}]", "TOOL")
    
    tool_lines.append("")
    
    await cl.Message(
        author=persona.get("persona_name", "Agent"),
        content="\n".join(tool_lines)
    ).send()


# =========================
# Humanized Message Builders
# =========================

def build_sarah_message(wo_id: str, equipment: str, issue_desc: str, severity: str, wo_type: str) -> str:
    """Sarah's conversational issue report"""
    greeting = random.choice(SARAH_GREETINGS)
    concern = random.choice(SARAH_CONCERNS.get(severity.lower(), SARAH_CONCERNS["medium"]))
    
    # Make severity more casual
    severity_casual = {
        "high": "pretty serious",
        "medium": "moderate concern",
        "low": "minor thing",
        "critical": "urgent"
    }.get(severity.lower(), "needs attention")
    
    return f"""
{greeting}

{concern}

**{equipment}** - Work Order {wo_id}

{issue_desc}

This looks like a **{severity_casual}** to me. I think we need to get {wo_type.lower()} maintenance scheduled for this.

David, can you take a look and assign someone?
"""


def build_david_message(wo_id: str, equipment: str, tech_name: str, tech_role: str, 
                        requires_loto: bool, safety_critical: bool) -> str:
    """David's conversational work assignment"""
    ack = random.choice(DAVID_ACKNOWLEDGMENTS)
    assignment = random.choice(DAVID_ASSIGNMENTS.get(tech_role, DAVID_ASSIGNMENTS["MMT"]))
    
    safety_notes = []
    if requires_loto:
        safety_notes.append("⚠️ **LOTO required** - coordinate with Robert before starting")
    if safety_critical:
        safety_notes.append("🔴 **Safety critical** - extra careful on this one")
    
    safety_section = "\n".join(safety_notes) if safety_notes else "Standard safety procedures apply."
    
    return f"""
{ack}

**Work Order {wo_id}** - {equipment}

{assignment}

{tech_name}, here's what you need to know:

{safety_section}

Let me know when you've reviewed it and what parts you'll need.
"""


def build_tech_planning_message(tech_name: str, tech_role: str, wo_id: str, 
                                equipment: str, desc: str, parts_count: int) -> str:
    """Technician's conversational work planning"""
    greetings = {
        "MMT": [
            "Hey everyone, Mike here.",
            "Mike checking in.",
            "This is Mike - got the work order.",
        ],
        "EMT": [
            "Eric here, reviewing the assignment.",
            "Hey, Eric looking at this now.",
            "This is Eric - checking out the work order.",
        ],
        "HT": [
            "Henry here - got the hydraulic job.",
            "Hey everyone, Henry on this one.",
            "This is Henry - reviewing the hydraulic work.",
        ]
    }
    
    greeting = random.choice(greetings.get(tech_role, greetings["MMT"]))
    ack = random.choice(TECH_ACKNOWLEDGMENTS["confident"] if parts_count <= 2 else TECH_ACKNOWLEDGMENTS["cautious"])
    
    return f"""
{greeting}

Just looked at **{wo_id}** for the {equipment}.

**Job:** {desc}

{ack}

{"Let me grab the parts list..." if parts_count > 0 else "Looks like I don't need any parts for this - just tools."}
"""


def build_tech_parts_request(tech_name: str, parts: List[Dict]) -> str:
    """Technician's casual parts request"""
    if len(parts) == 1:
        intro = "Mira, I just need one part for this job:"
    elif len(parts) == 2:
        intro = "Mira, can you grab me a couple parts?"
    else:
        intro = f"Mira, I need {len(parts)} parts from the store:"
    
    parts_list = []
    for part in parts:
        part_code = part.get('part_code', part.get('part_id', 'Unknown'))
        part_name = part.get('part_name', part.get('part_description', 'Unknown part'))
        qty = part.get('required_quantity', 0)
        
        qty_text = f"{int(qty)} piece" if qty == 1 else f"{int(qty)} pieces"
        parts_list.append(f"• **{part_code}** - {part_name} ({qty_text})")
    
    return f"""
### 🔧 **Parts Request**

{intro}

{chr(10).join(parts_list)}

Let me know if you have them in stock!
"""


def build_mira_response(spares_issued: int, parts_available: List[str], 
                         parts_unavailable: List[str]) -> str:
    """Mira's conversational parts response"""
    greeting = random.choice(MIRA_GREETINGS)
    
    if not parts_unavailable:
        good_news = random.choice(MIRA_GOOD_NEWS)
        return f"""
{greeting}

{good_news}

✅ **Issued {spares_issued} item(s)** - Parts are ready for pickup at the maintenance store.

Come grab them whenever you're ready to start!
"""
    else:
        bad_news = random.choice(MIRA_BAD_NEWS)
        return f"""
{greeting}

{bad_news}

Here's the situation:

✅ **Available:** {len(parts_available)} part(s) - These are ready to go
❌ **Out of stock:** {len(parts_unavailable)} part(s) - I'll need to order these

I'm creating purchase requisitions right now for the missing parts. I'll ping you when they arrive!
"""


def build_james_recommendation(wo_id: str, equipment: str, tech_name: str, 
                                parts_available: bool, purchase_requests: List[Dict]) -> Dict[str, str]:
    """James's pre-approval recommendation for human decision"""
    
    if parts_available:
        recommendation = "APPROVE"
        icon = "✅"
        reason = f"{tech_name} has completed the work successfully. All required parts were available and issued. Equipment has been tested and is ready for operation."
        next_steps = "Close this work order and return equipment to service. Next preventive maintenance will be scheduled automatically."
    else:
        recommendation = "PUT ON HOLD"
        icon = "⏸️"
        
        pr_count = len(purchase_requests)
        pr_list = ", ".join([pr.get('pr_id', 'N/A') for pr in purchase_requests[:3]])
        if pr_count > 3:
            pr_list += f", and {pr_count - 3} more"
        
        reason = f"Required spare parts are not available in inventory. {pr_count} purchase requisition(s) created: {pr_list}. Work cannot proceed until parts arrive."
        next_steps = "Wait for procurement to fulfill purchase requisitions. Once parts arrive, Mira will notify the team and work can resume."
    
    summary = f"""
### {icon} **James's Recommendation: {recommendation}**

**Work Order:** {wo_id} - {equipment}  
**Technician:** {tech_name}

**📊 Analysis:**

{reason}

**🔮 Next Steps:**

{next_steps}

---

**👤 Your Decision Required**

Please review the information above and make your decision:
"""
    
    return {
        "summary": summary,
        "recommendation": recommendation,
        "icon": icon
    }


def build_james_summary(wo_id: str, equipment: str, wo_type: str, 
                        tech_name: str, parts_count: int, status: str, 
                        purchase_requests: List[Dict] = None) -> str:
    """James's conversational summary - handles ON HOLD status properly"""
    greeting = random.choice(JAMES_GREETINGS)
    
    # Status message
    if status == 'closed':
        status_msg = "✅ **All done and closed!**"
        conclusion = f"The {equipment} is back up and running. {tech_name} did a solid job on this one."
        workflow = f"""
**Sarah** spotted the issue during her rounds and flagged it
↓
**David** reviewed it and assigned {tech_name} to handle it
↓
**{tech_name}** planned the work and requested {parts_count} part(s)
↓
**Mira** checked inventory and issued the parts
↓
**Robert** did the final safety check and approved closure
"""
        
    elif status == 'blocked':
        status_msg = "⏸️ **ON HOLD - Awaiting Parts**"
        
        # Build parts list
        if purchase_requests:
            parts_list = []
            for pr in purchase_requests:
                part_code = pr.get('part_code', 'Unknown')
                qty = pr.get('requested_qty', 0)
                pr_id = pr.get('pr_id', 'N/A')
                parts_list.append(f"  - **{part_code}** (Qty: {int(qty)}) - PR: {pr_id}")
            parts_text = "\n".join(parts_list)
        else:
            parts_text = "  - Parts info not available"
        
        conclusion = f"""
⚠️ **This work order cannot proceed yet.**

**Missing Parts:**
{parts_text}

**What's Next:**
1. Procurement team will order the missing parts
2. Mira will notify us when parts arrive
3. {tech_name} can then complete the work
4. Robert will do the final safety check

**I'll update everyone once we can continue with this work.**
"""
        
        workflow = f"""
**Sarah** spotted the issue during her rounds and flagged it
↓
**David** reviewed it and assigned {tech_name} to handle it
↓
**{tech_name}** planned the work and requested {parts_count} part(s)
↓
**Mira** checked inventory - **PARTS UNAVAILABLE** ❌
↓
**Created {len(purchase_requests) if purchase_requests else 0} purchase requisition(s)**
"""
        
    else:
        status_msg = "🔄 **Still in progress**"
        conclusion = f"Work is ongoing. I'll keep everyone posted."
        workflow = "**Work in progress...**"
    
    return f"""
{greeting}

# 📋 **Work Order {wo_id} - {equipment}**

{status_msg}

**What Happened:**

{workflow}

---

{conclusion}

That's the current status for {wo_id}!
"""

async def render_enhanced_summary(result_state, wo_id, equipment, wo_type):
    """Enhanced summary rendering with humanized James intro"""
    
    # Visual separator before summary
    await cl.Message(
        author="System",
        content="---\n\n# 📊 **COMPLETE WORK ORDER SUMMARY**\n\n---"
    ).send()
    
    await asyncio.sleep(0.3)
    
    final_answer = result_state.get('final_answer')
    
    # Determine status
    if result_state.get('wo_closed'):
        status = 'closed'
    elif result_state.get('purchase_required'):
        status = 'blocked'
    else:
        status = 'in_progress'
    
    # Get execution details
    tech_name = result_state.get('technician_name', 'the technician')
    parts_count = len(result_state.get('required_parts', []))
    purchase_requests = result_state.get('purchase_requests', [])
    
    # James's casual intro
    purchase_requests = result_state.get('purchase_requests', [])
    james_intro = build_james_summary(wo_id, equipment, wo_type, tech_name, parts_count, status, purchase_requests)
    
    if final_answer:
        # Show James's casual intro, then detailed LLM summary
        await render_persona_message("summary_agent", james_intro).send()
        await asyncio.sleep(0.3)
        await render_persona_message("summary_agent", f"\n---\n\n## **Detailed Breakdown**\n\n{final_answer}").send()
    else:
        # Enhanced fallback summary
        summary_parts = [james_intro, "\n---\n"]
        
        # Add detailed sections
        summary_parts.append(f"## **Full Details**\n")
        
        # Team collaboration
        execution_path = result_state.get("execution_path", [])
        if execution_path:
            summary_parts.append(f"### 👥 **Team Contributions**\n")
            
            if "operator_agent" in execution_path:
                issue_desc = result_state.get('issue_description', 'Equipment issue detected')
                summary_parts.append(f"- **Sarah:** {issue_desc}")
                
            if "supervisor_agent" in execution_path:
                assigned_role = result_state.get('assigned_technician', 'MMT')
                summary_parts.append(f"- **David:** Work assignment to {tech_name} ({assigned_role})")
                
            if "technician_agent" in execution_path:
                summary_parts.append(f"- **{tech_name}:** Work planning and execution")
                
            if "inventory_agent" in execution_path:
                inventory_context = result_state.get('inventory_context', {})
                spares_issued = inventory_context.get('spares_issued', 0)
                summary_parts.append(f"- **Mira:** Parts management ({spares_issued} issued)")
                
            summary_parts.append("")
        
        # Parts details
        if result_state.get("required_parts"):
            summary_parts.append(f"### 📦 **Parts Used**\n")
            
            for part in result_state.get("required_parts", []):
                part_code = part.get('part_code', part.get('part_id', 'Unknown'))
                part_name = part.get('part_name', part.get('part_description', 'Unknown part'))
                qty = part.get('required_quantity', 0)
                summary_parts.append(f"- **{part_code}**: {part_name} (Qty: {int(qty)})")
            
            summary_parts.append("")
        
        # Execution metrics
        summary_parts.append(f"### 📊 **Quick Stats**\n")
        summary_parts.append(f"- Agents involved: {len(execution_path)}/6")
        summary_parts.append(f"- System operations: {len(result_state.get('tool_calls', []))}")
        
        await render_persona_message("summary_agent", "\n".join(summary_parts)).send()

    await asyncio.sleep(0.5)


# =========================
# Main rendering function
# =========================

async def render_maintenance_results(result_state: MaintenanceState):
    """Render complete role-based maintenance journey with humanized messages"""
    
    # Safe getter
    def safe_get(d, key, default=None):
        if d is None:
            return default
        return d.get(key, default)
    
    wo = result_state.get("work_order") or {}
    wo_id = safe_get(wo, "work_order_id", "Unknown")
    equipment = safe_get(wo, "equipment_name", "Unknown")
    wo_type = safe_get(wo, "wo_type", "Unknown")
    desc = safe_get(wo, "description", "No description")
    
    execution_path = result_state.get("execution_path") or []
    all_tool_calls = result_state.get("tool_calls") or []
    errors = result_state.get("errors") or []
    
    log_to_terminal(f"=== RENDERING RESULTS FOR {wo_id} ===", "INFO")
    log_to_terminal(f"Execution path: {' → '.join(execution_path)}", "INFO")

    # ==========================================
    # PHASE 1: OPERATOR (Sarah) - Issue Detection
    # ==========================================
    
    if "operator_agent" in execution_path:
        # Work order context card
        context_card = f"""
### 📋 **Work Order Details**

- **ID:** {wo_id}  
- **Equipment:** {equipment}  
- **Type:** {wo_type}  
- **Description:** {desc}
"""
        
        await render_persona_message("operator_agent", context_card).send()
        await asyncio.sleep(0.3)
        
        # Operator thinking (optional - can be shown or hidden)
        issue_desc = result_state.get("issue_description", "Routine maintenance required")
        severity = result_state.get("severity", "Medium")
        
        thinking = f"""
Reviewing work order {wo_id}...

Equipment: {equipment}
Work type: {wo_type}

Observation: {issue_desc}
Severity Assessment: {severity}

Reporting to supervisor for work assignment.
"""
        await show_agent_thinking("operator_agent", thinking)
        
        # HUMANIZED: Sarah's conversational message
        operator_msg = build_sarah_message(wo_id, equipment, issue_desc, severity, wo_type)
        await render_persona_message("operator_agent", operator_msg).send()
        
        # Tool usage
        operator_tools = [tc for tc in all_tool_calls if "operator" in tc.get("agent_name", "")]
        await show_tool_usage("operator_agent", operator_tools)
        
        await asyncio.sleep(0.5)

    # ==========================================
    # PHASE 2: SUPERVISOR (David) - Work Assignment
    # ==========================================
    
    if "supervisor_agent" in execution_path:
        assigned_tech = result_state.get("assigned_technician", "MMT")
        tech_name = result_state.get("technician_name", "Mike")
        requires_loto = result_state.get("requires_lockout", False)
        safety_critical = result_state.get("safety_critical", False)
        
        thinking = f"""
Analyzing work order requirements...

Equipment: {equipment}
Work type: {wo_type}

Assignment Analysis:
- Technical discipline: {assigned_tech}
- Assigned to: {tech_name}
- Requires LOTO: {requires_loto}
- Safety critical: {safety_critical}

Coordinating with technician and safety officer.
"""
        await show_agent_thinking("supervisor_agent", thinking)
        
        # HUMANIZED: David's conversational assignment
        supervisor_msg = build_david_message(wo_id, equipment, tech_name, assigned_tech, 
                                             requires_loto, safety_critical)
        await render_persona_message("supervisor_agent", supervisor_msg).send()
        
        # Tool usage
        supervisor_tools = [tc for tc in all_tool_calls if "supervisor" in tc.get("agent_name", "")]
        await show_tool_usage("supervisor_agent", supervisor_tools)
        
        await asyncio.sleep(0.5)

    # ==========================================
    # PHASE 3: TECHNICIAN (Mike/Eric/Henry) - Work Planning
    # ==========================================
    
    if "technician_agent" in execution_path:
        tech_role = result_state.get("assigned_technician", "MMT")
        tech_name = result_state.get("technician_name", "Mike")
        tech_context = result_state.get("technician_context") or {}
        
        # Get technician persona
        tech_persona = get_technician_persona(tech_role)
        
        # HUMANIZED: Technician's conversational intro
        parts_count = len(result_state.get('required_parts', []))
        intro_msg = build_tech_planning_message(tech_name, tech_role, wo_id, equipment, desc, parts_count)
        
        # Add avatar
        full_intro = f"{intro_msg}\n\n![{tech_name}'s Avatar]({tech_persona.get('avatar_url', '')})"
        
        await cl.Message(
            author=tech_name,
            content=full_intro
        ).send()
        
        await asyncio.sleep(0.3)
        
        # Technician thinking
        tasks = safe_get(tech_context, 'tasks_planned', [])
        parts = safe_get(tech_context, 'parts_requested', [])
        est_time = safe_get(tech_context, 'estimated_time', '2-3 hours')
        
        thinking = f"""
Planning my work...

Tasks to perform:
{chr(10).join([f"- {task}" for task in tasks]) if tasks else "- Standard maintenance procedure"}

Parts needed: {parts_count} items
Estimated time: {est_time}

Checking with Mira (Storekeeper) for parts availability.
"""
        
        # Show thinking under technician's name
        thinking_content = f"""
<details>
<summary><b>💭 {tech_name}'s Planning Process</b></summary>

```
{thinking}
```

</details>
"""
        await cl.Message(author=tech_name, content=thinking_content).send()
        
        # HUMANIZED: Technician's casual parts request
        required_parts = result_state.get("required_parts", [])
        if required_parts:
            parts_msg = build_tech_parts_request(tech_name, required_parts)
            await cl.Message(author=tech_name, content=parts_msg).send()
        
        # Tool usage
        tech_tools = [tc for tc in all_tool_calls if "technician" in tc.get("agent_name", "")]
        await show_tool_usage("technician_agent", tech_tools)
        
        await asyncio.sleep(0.5)

    # ==========================================
    # PHASE 4: INVENTORY (Mira) - Parts Management
    # ==========================================
    
    if "inventory_agent" in execution_path:
        inventory_context = result_state.get("inventory_context") or {}
        
        # Thinking
        thinking = f"""
Checking spare parts availability...

Parts requested: {safe_get(inventory_context, 'spares_checked', 0)}
Available in stock: {safe_get(inventory_context, 'spares_available', 0)}
Need to issue: {safe_get(inventory_context, 'spares_issued', 0)}
Shortages: {len(safe_get(inventory_context, 'shortages', []))}

Processing issue transactions...
"""
        await show_agent_thinking("inventory_agent", thinking)
        
        # Tool usage
        inventory_tools = [tc for tc in all_tool_calls if "inventory" in tc.get("agent_name", "")]
        await show_tool_usage("inventory_agent", inventory_tools)
        
        # Material table
        inventory = result_state.get("inventory_status") or {}
        required_parts = result_state.get("required_parts") or []
        reservation_status = result_state.get("reservation_status") or {}
        
        if required_parts:
            table = _material_readiness_table(required_parts, inventory)
            
            # Show table first
            summary_parts = []
            summary_parts.append(f"📦 **Spare Parts Status**\n")
            summary_parts.append(table)
            summary_parts.append("")
            
            await render_persona_message("inventory_agent", "\n".join(summary_parts)).send()
            await asyncio.sleep(0.3)
            
            # HUMANIZED: Mira's conversational response
            spares_issued = safe_get(inventory_context, "spares_issued", 0)
            parts_available = [p for p, s in reservation_status.items() if s.get("status") == "Issued"]
            parts_unavailable = [p for p, s in reservation_status.items() if s.get("status") == "Not Available"]
            
            mira_msg = build_mira_response(spares_issued, parts_available, parts_unavailable)
            
            # Add PR details if any
            purchase_requests = result_state.get("purchase_requests", [])
            if purchase_requests:
                mira_msg += "\n\n**Purchase Requisitions Created:**\n"
                for pr in purchase_requests:
                    pr_id = pr.get("pr_id", "N/A")
                    part_code = pr.get("part_code", "N/A")
                    qty = pr.get("requested_qty", 0)
                    mira_msg += f"- **{pr_id}**: {part_code} (Qty: {int(qty)})\n"
            
            await render_persona_message("inventory_agent", mira_msg).send()
        
        await asyncio.sleep(0.5)

    # ==========================================
    # PHASE 6: SUMMARY (James) - Complete Journey
    # ==========================================
    
    await render_enhanced_summary(result_state, wo_id, equipment, wo_type)
    
    # ==========================================
    # PHASE 7: EXECUTION FLOW
    # ==========================================
    
    flow_lines = ["**🔀 Work Order Journey**\n"]
    
    agent_display = [
        ("operator_agent", "Sarah (Operator)", "🔍"),
        ("supervisor_agent", "David (Supervisor)", "💼"),
        ("technician_agent", result_state.get("technician_name", "Technician") + " (Technician)", "🔧"),
        ("inventory_agent", "Mira (Storekeeper)", "📦"),
        ("summary_agent", "James (Coordinator)", "📊"),
    ]
    
    for agent_key, agent_name, emoji in agent_display:
        if agent_key in execution_path:
            flow_lines.append(f"{emoji} **{agent_name}** - Executed")
        else:
            flow_lines.append(f"⚪ {agent_name} - Skipped")
    
    await cl.Message(author="System", content="\n".join(flow_lines)).send()
    
    log_to_terminal(f"Execution complete. Path: {' → '.join(execution_path)}", "SUCCESS")

    # ==========================================
    # PHASE 8: ERRORS
    # ==========================================
    
    if errors:
        error_lines = ["**⚠️ Issues Encountered**\n"]
        
        for error in errors:
            agent = error.get("agent", "Unknown")
            error_type = error.get("error_type", "Error")
            recoverable = error.get("recoverable", True)
            
            icon = "🟡" if recoverable else "🔴"
            error_lines.append(f"{icon} **{agent}**: {error_type}")
        
        error_lines.append("\n✅ System continued with graceful degradation.")
        await cl.Message(author="System", content="\n".join(error_lines)).send()

    # ==========================================
    # PHASE 9: METRICS
    # ==========================================
    
    total_tools = len(all_tool_calls)
    agents_executed = len(execution_path)
    
    metrics = f"""
**📊 Performance Metrics**

• **Agents Executed:** {agents_executed}/6
• **Tool Calls Made:** {total_tools}
• **Journey:** {'✅ Complete' if agents_executed == 6 else '⚠️ Partial'}
"""
    
    log_to_terminal(f"Metrics - Agents: {agents_executed}/6, Tools: {total_tools}", "INFO")
    
    await cl.Message(author="System", content=metrics).send()


# =========================
# Work order processing
# =========================

async def process_single_work_order(work_order_id: str, user_input: str):
    """Process a single work order with REAL-TIME agent output rendering"""
    
    log_to_terminal(f"=== STARTING PROCESSING: {work_order_id} ===", "INFO")
    
    state = initialize_state(user_query=user_input, work_order_id=work_order_id)
    
    # Get work order info for rendering
    wo = state.get("work_order") or {}
    wo_id = wo.get("work_order_id", work_order_id)
    equipment = wo.get("equipment_name", "Unknown")
    wo_type = wo.get("wo_type", "Unknown")
    desc = wo.get("description", "No description")
    
    # Create unique thread_id for checkpointing
    thread_id = f"wo-{wo_id}-{cl.context.session.id[:8]}"
    config = {"configurable": {"thread_id": thread_id}}
    
    # Store in session for continuation
    cl.user_session.set("thread_id", thread_id)
    cl.user_session.set("wo_info", {
        "wo_id": wo_id,
        "equipment": equipment,
        "wo_type": wo_type,
        "desc": desc
    })
    
    processing_msg = await cl.Message(
        author="System",
        content=f"🔄 **Processing work order {work_order_id}**\n\nInitializing agent team..."
    ).send()
    
    await asyncio.sleep(0.5)
    
    try:
        log_to_terminal("Invoking LangGraph with streaming...", "INFO")
        
        # Agent names for progress tracking
        agent_names = {
            "operator_agent": "📝 Sarah (Operator)",
            "supervisor_agent": "💼 David (Supervisor)",
            "technician_agent": "🔧 Technician",
            "inventory_agent": "📦 Mira (Storekeeper)",
            "pre_approval_summary": "📊 James (Pre-Approval)",
            "human_approval": "👤 Human Decision",
            "summary_agent": "📊 James (Summary)"
        }
        
        result_state = None
        completed_agents = []
        
        # Stream through the graph and show progress
        for chunk in graph.stream(state, config):
            if not chunk:
                continue
            
            # Get current state
            node_name = list(chunk.keys())[0]
            current_state = chunk[node_name]            
            # Check if we hit the interrupt point
            if node_name == "__interrupt__":
                interrupted = True
                log_to_terminal("Graph interrupted - waiting for human approval", "INFO")
                await processing_msg.remove()
                return  # Stop here - wait for button click

            result_state = current_state
            
            # Check execution path
            execution_path = current_state.get("execution_path", [])
            
            # Find newly completed agents
            for agent in execution_path:
                if agent not in completed_agents:
                    completed_agents.append(agent)
                    
                    log_to_terminal(f"✅ {agent} completed - rendering output now", "SUCCESS")
                    
                    # Update progress message
                    await processing_msg.remove()
                    progress = f"🔄 **Progress:** {len(completed_agents)}/6 agents\n\n"
                    for done_agent in completed_agents:
                        progress += f"✅ {agent_names.get(done_agent, done_agent)}\n"
                    processing_msg = await cl.Message(author="System", content=progress).send()
                    
                    await asyncio.sleep(0.2)
                    
                    # ============================================
                    # RENDER THIS AGENT'S OUTPUT IMMEDIATELY
                    # ============================================
                    
                    await render_agent_output(agent, current_state, wo_id, equipment, wo_type, desc)
                    
                    await asyncio.sleep(0.3)
        
        # If no streaming happened, fall back to regular invoke
        if result_state is None:
            log_to_terminal("Streaming didn't work, using regular invoke", "WARNING")
            result_state = graph.invoke(state)
        
        log_to_terminal("LangGraph execution complete", "SUCCESS")
        
        # Store state in session for human approval continuation
        cl.user_session.set("current_state", result_state)
        
        # Check if waiting for human approval
        approval_context = result_state.get("human_approval_context", {})
        if approval_context.get("awaiting_approval", False):
            log_to_terminal("Pausing execution - awaiting human approval", "INFO")
            return  # Don't proceed to final summary yet - wait for button click
        
        # Remove progress message
        await processing_msg.remove()
        
        # Show final execution flow and metrics
        await render_final_summary(result_state)
    
    except Exception as e:
        log_to_terminal(f"CRITICAL ERROR: {str(e)}", "ERROR")
        try:
            await processing_msg.remove()
        except:
            pass
        await cl.Message(
            author="System",
            content=f"❌ **Critical Error**\n\n{str(e)}\n\nPlease try again or contact support."
        ).send()
        import traceback
        traceback.print_exc()


async def render_agent_output(agent_name: str, state: Dict, wo_id: str, equipment: str, wo_type: str, desc: str):
    """
    Render a single agent's output immediately after it completes.
    This is called in real-time as agents finish.
    """
    
    def safe_get(d, key, default=None):
        if d is None:
            return default
        return d.get(key, default)
    
    all_tool_calls = state.get("tool_calls", [])
    
    # ==========================================
    # OPERATOR (Sarah)
    # ==========================================
    if agent_name == "operator_agent":
        issue_desc = state.get("issue_description", "Routine maintenance required")
        severity = state.get("severity", "Medium")
        
        # Work order details
        context_card = f"""
### 📋 **Work Order Details**

- **ID:** {wo_id}  
- **Equipment:** {equipment}  
- **Type:** {wo_type}  
- **Description:** {desc}
"""
        await render_persona_message("operator_agent", context_card).send()
        await asyncio.sleep(0.2)
        
        # Show thinking process
        thinking = f"""
Reviewing work order {wo_id}...

Equipment: {equipment}
Work type: {wo_type}

Observation: {issue_desc}
Severity Assessment: {severity}

Reporting to supervisor for work assignment.
"""
        await show_agent_thinking("operator_agent", thinking)
        
        # Sarah's message
        operator_msg = build_sarah_message(wo_id, equipment, issue_desc, severity, wo_type)
        await render_persona_message("operator_agent", operator_msg).send()
    
    # ==========================================
    # SUPERVISOR (David)
    # ==========================================
    elif agent_name == "supervisor_agent":
        tech_name = state.get("technician_name", "Mike")
        tech_role = state.get("assigned_technician", "MMT")
        requires_loto = state.get("requires_lockout", False)
        safety_critical = state.get("safety_critical", False)
        
        # Show thinking process
        thinking = f"""
Analyzing work order requirements...

Equipment: {equipment}
Work type: {wo_type}

Assignment Analysis:
- Technical discipline: {tech_role}
- Assigned to: {tech_name}
- Requires LOTO: {requires_loto}
- Safety critical: {safety_critical}

Coordinating with technician and safety officer.
"""
        await show_agent_thinking("supervisor_agent", thinking)
        
        supervisor_msg = build_david_message(wo_id, equipment, tech_name, tech_role, requires_loto, safety_critical)
        await render_persona_message("supervisor_agent", supervisor_msg).send()
    
    # ==========================================
    # TECHNICIAN (Mike/Eric/Henry)
    # ==========================================
    elif agent_name == "technician_agent":
        tech_name = state.get("technician_name", "Mike")
        tech_role = state.get("assigned_technician", "MMT")
        tech_persona = get_technician_persona(tech_role)
        tech_context = state.get("technician_context") or {}
        parts_count = len(state.get('required_parts', []))
        
        # Tech intro
        intro_msg = build_tech_planning_message(tech_name, tech_role, wo_id, equipment, desc, parts_count)
        full_intro = f"{intro_msg}\n\n![{tech_name}'s Avatar]({tech_persona.get('avatar_url', '')})"
        await cl.Message(author=tech_name, content=full_intro).send()
        await asyncio.sleep(0.2)
        
        # Show thinking process
        tasks = tech_context.get('tasks_planned', [])
        est_time = tech_context.get('estimated_time', '2-3 hours')
        
        thinking = f"""
Planning my work...

Tasks to perform:
{chr(10).join([f"- {task}" for task in tasks]) if tasks else "- Standard maintenance procedure"}

Parts needed: {parts_count} items
Estimated time: {est_time}

Checking with Mira (Storekeeper) for parts availability.
"""
        
        thinking_content = f"""
<details>
<summary><b>💭 {tech_name}'s Planning Process</b></summary>

```
{thinking}
```

</details>
"""
        await cl.Message(author=tech_name, content=thinking_content).send()
        
        # Parts request
        required_parts = state.get("required_parts", [])
        if required_parts:
            parts_msg = build_tech_parts_request(tech_name, required_parts)
            await cl.Message(author=tech_name, content=parts_msg).send()
    
    # ==========================================
    # INVENTORY (Mira)
    # ==========================================
    elif agent_name == "inventory_agent":
        inventory_context = state.get("inventory_context", {})
        reservation_status = state.get("reservation_status", {})
        inventory = state.get("inventory_status", {})
        required_parts = state.get("required_parts", [])
        
        # Calculate actual issued count from reservation_status
        parts_available = [p for p, s in reservation_status.items() if s.get("status") == "Issued"]
        parts_unavailable = [p for p, s in reservation_status.items() if s.get("status") == "Not Available"]
        spares_issued = len(parts_available)
        
        # Show thinking process (use calculated values if context is empty)
        thinking = f"""
Checking spare parts availability...

Parts requested: {safe_get(inventory_context, 'spares_checked', len(required_parts))}
Available in stock: {safe_get(inventory_context, 'spares_available', len(parts_available))}
Need to issue: {spares_issued}
Shortages: {len(parts_unavailable)}

Processing issue transactions...
"""
        await show_agent_thinking("inventory_agent", thinking)
        
        # Show parts table
        if required_parts:
            table = _material_readiness_table(required_parts, inventory)
            await render_persona_message("inventory_agent", f"📦 **Spare Parts Status**\n\n{table}\n").send()
            await asyncio.sleep(0.2)
        
        # Mira's response with correct count
        mira_msg = build_mira_response(spares_issued, parts_available, parts_unavailable)
        
        # Add PRs if any
        purchase_requests = state.get("purchase_requests", [])
        if purchase_requests:
            mira_msg += "\n\n**Purchase Requisitions Created:**\n"
            for pr in purchase_requests:
                pr_id = pr.get("pr_id", "N/A")
                part_code = pr.get("part_code", "N/A")
                qty = pr.get("requested_qty", 0)
                mira_msg += f"- **{pr_id}**: {part_code} (Qty: {int(qty)})\n"
        
        await render_persona_message("inventory_agent", mira_msg).send()
    
    
    # ==========================================
    # PRE-APPROVAL SUMMARY (James gives recommendation)
    # ==========================================
    elif agent_name == "pre_approval_summary":
        tech_name = state.get("technician_name", "the technician")
        parts_available = not state.get("purchase_required", False)
        purchase_requests = state.get("purchase_requests", [])
        
        # Get James's recommendation
        recommendation_data = build_james_recommendation(
            wo_id, equipment, tech_name, parts_available, purchase_requests
        )
        
        # Show James's recommendation
        await cl.Message(
            author="James",
            content=recommendation_data["summary"]
        ).send()
        
        await asyncio.sleep(0.5)
        
        # CREATE ACTION BUTTONS FOR HUMAN APPROVAL
        actions = [
            cl.Action(
                name="approve_wo",
                value="approve",
                payload={"work_order_id": wo_id},
                label="✅ Approve",
                description="Close work order and return equipment to service"
            ),
            cl.Action(
                name="hold_wo",
                value="hold",
                payload={"work_order_id": wo_id},
                label="⏸️ Put ON HOLD",
                description="Keep work order open - awaiting parts or further action"
            )
        ]
        
        await cl.Message(
            author="System",
            content="**👤 Awaiting your decision...**",
            actions=actions
        ).send()
        
        log_to_terminal(f"Waiting for human approval on {wo_id}", "INFO")
    
    # ==========================================
    # HUMAN APPROVAL (User's decision recorded)
    # ==========================================
    elif agent_name == "human_approval":
        approval_context = state.get("human_approval_context", {})
        human_decision = approval_context.get("human_decision", "")
        human_notes = approval_context.get("human_notes", "")
        
        if human_decision == "APPROVED":
            decision_msg = f"""
### ✅ **Work Order APPROVED**

You have approved this work order for closure.

**Equipment Status:** Ready for operation  
**Next Steps:** Equipment returned to service, next PM will be scheduled automatically

{f"**Your Notes:** {human_notes}" if human_notes else ""}
"""
        elif human_decision == "ON_HOLD":
            decision_msg = f"""
### ⏸️ **Work Order ON HOLD**

You have placed this work order on hold.

**Status:** Work cannot proceed yet  
**Next Steps:** Awaiting parts/procurement or further action required

{f"**Your Notes:** {human_notes}" if human_notes else ""}
"""
        else:
            decision_msg = "Decision recorded."
        
        await cl.Message(
            author="System",
            content=decision_msg
        ).send()
        
        log_to_terminal(f"Human decision: {human_decision}", "SUCCESS")

    # ==========================================
    # SUMMARY (James)
    # ==========================================
    elif agent_name == "summary_agent":
        # Show separator
        await cl.Message(
            author="System",
            content="---\n\n# 📊 **COMPLETE WORK ORDER SUMMARY**\n\n---"
        ).send()
        await asyncio.sleep(0.2)
        
        # James's summary
        status = 'closed' if state.get('wo_closed') else 'blocked' if state.get('purchase_required') else 'in_progress'
        tech_name = state.get('technician_name', 'the technician')
        parts_count = len(state.get('required_parts', []))
        purchase_requests = state.get('purchase_requests', [])
        
        purchase_requests = state.get('purchase_requests', [])
        james_msg = build_james_summary(wo_id, equipment, wo_type, tech_name, parts_count, status, purchase_requests)
        await render_persona_message("summary_agent", james_msg).send()


async def render_final_summary(result_state: Dict):
    """Render final execution flow and metrics"""
    
    execution_path = result_state.get("execution_path", [])
    
    # Execution flow
    flow_lines = ["**🔀 Work Order Journey**\n"]
    
    agent_display = [
        ("operator_agent", "Sarah (Operator)", "🔍"),
        ("supervisor_agent", "David (Supervisor)", "💼"),
        ("technician_agent", result_state.get("technician_name", "Technician") + " (Technician)", "🔧"),
        ("inventory_agent", "Mira (Storekeeper)", "📦"),
        ("summary_agent", "James (Coordinator)", "📊"),
    ]
    
    for agent_key, agent_name, emoji in agent_display:
        if agent_key in execution_path:
            flow_lines.append(f"{emoji} **{agent_name}** - Executed")
        else:
            flow_lines.append(f"⚪ {agent_name} - Skipped")
    
    await cl.Message(author="System", content="\n".join(flow_lines)).send()
    
    # Metrics
    total_tools = len(result_state.get("tool_calls", []))
    agents_executed = len(execution_path)
    
    metrics = f"""
**📊 Performance Metrics**

• **Agents Executed:** {agents_executed}/6
• **Tool Calls Made:** {total_tools}
• **Journey:** {'✅ Complete' if agents_executed == 6 else '⚠️ Partial'}
"""
    
    await cl.Message(author="System", content=metrics).send()
    
    log_to_terminal(f"Final summary rendered. Total agents: {agents_executed}", "SUCCESS")


# =========================
# Chainlit handlers
# =========================

@cl.on_chat_start
async def on_chat_start():
    """Beautiful welcome screen"""
    
    log_to_terminal("=== NEW SESSION STARTED ===", "INFO")
    try:
        log_to_terminal(f"Session ID: {cl.context.session.id}", "INFO")
    except:
        pass
    
    welcome = """
# **🔧 Role-Based Maintenance Planning System**

Welcome to the **Rubber Recycling Plant** maintenance planning assistant!

## **Meet Your Maintenance Team**

Our AI-powered team manages the complete maintenance workflow with **natural, human-like conversations**...
"""
    
    await cl.Message(author="System", content=welcome).send()
    await asyncio.sleep(0.5)
    
    # Show each agent
    agents_info = [
        ("operator_agent", "📝", "Monitors equipment and reports issues"),
        ("supervisor_agent", "💼", "Creates work orders and assigns technicians"),
        ("technician_agent", "🔧", "Plans and executes maintenance work"),
        ("inventory_agent", "📦", "Manages spare parts and inventory"),
        ("pre_approval_summary", "📊", "James provides recommendation"),
        ("human_approval", "👤", "YOU make the final decision"),
        ("summary_agent", "📊", "Final summary and journey"),
    ]
    
    for agent_key, emoji, description in agents_info:
        persona = PERSONAS.get(agent_key, {})
        
        # Skip agents that don't have persona entries (pre_approval_summary, human_approval)
        if agent_key in ["pre_approval_summary", "human_approval"]:
            agent_card = f"""
### {emoji} **{description}**

{description}
"""
        else:
            persona_name = persona.get('persona_name', 'Agent')
            display_name = persona.get('display_name', '')
            avatar_url = persona.get('avatar_url', '')
            tone = persona.get('tone', 'Professional')
            
            agent_card = f"""
### {emoji} {persona_name} - *{display_name}*
![{persona_name}]({avatar_url})
**Role:** {description}  
**Style:** {tone}
"""
        
        await cl.Message(author=persona.get('persona_name', 'System'), content=agent_card).send()
        await asyncio.sleep(0.3)
    
    await asyncio.sleep(0.5)
    
    instructions = """
---

## **How to Use**

I can help you execute maintenance work orders for:
- **Primary Shredder (PS)** - Rubber shredding equipment
- **Air Compressor (AC)** - Compressed air system

**💬 Try These Examples:**
```
• "Execute WO-PS-015" (Hydraulic filter change)
• "Execute WO-PS-025" (Bearing replacement)
• "Execute WO-AC-018" (Electrical maintenance)
• "Show me all work orders"
```

**Ready to start?** Just type a work order ID! 🚀
"""
    
    await cl.Message(author="System", content=instructions).send()
    log_to_terminal("Welcome screen displayed", "SUCCESS")




# =========================
# Human Approval Action Handlers
# =========================

@cl.action_callback("approve_wo")
async def on_approve_action(action: cl.Action):
    """Handle Approve button click"""
    wo_id = action.payload.get("work_order_id")
    
    log_to_terminal(f"User APPROVED work order {wo_id}", "SUCCESS")
    
    # Store decision
    cl.user_session.set("human_decision", "APPROVED")
    cl.user_session.set("human_decision_wo", wo_id)
    
    # Remove buttons
    await action.remove()
    
    # Show feedback
    await cl.Message(
        author="System",
        content=f"✅ **You have APPROVED work order {wo_id}**\n\nProcessing your decision..."
    ).send()
    
    # Continue execution
    await continue_after_approval(wo_id, "APPROVED", "")


@cl.action_callback("hold_wo")
async def on_hold_action(action: cl.Action):
    """Handle Put ON HOLD button click"""
    wo_id = action.payload.get("work_order_id")
    
    log_to_terminal(f"User put work order {wo_id} ON HOLD", "WARNING")
    
    # Ask for optional notes
    res = await cl.AskUserMessage(
        content=f"📋 **Optional:** Add notes explaining why {wo_id} is on hold:",
        timeout=60
    ).send()
    
    notes = res.get("output", "") if res else ""
    
    # Store decision
    cl.user_session.set("human_decision", "ON_HOLD")
    cl.user_session.set("human_decision_wo", wo_id)
    cl.user_session.set("human_decision_notes", notes)
    
    # Remove buttons
    await action.remove()
    
    # Show feedback
    await cl.Message(
        author="System",
        content=f"⏸️ **You have placed work order {wo_id} ON HOLD**\n\nProcessing your decision..."
    ).send()
    
    # Continue execution
    await continue_after_approval(wo_id, "ON_HOLD", notes)


async def continue_after_approval(wo_id: str, decision: str, notes: str):
    """Continue graph execution after human approval using LangGraph resume"""
    
    # Get thread_id from session
    thread_id = cl.user_session.get("thread_id")
    wo_info = cl.user_session.get("wo_info", {})
    
    if not thread_id:
        await cl.Message(
            author="System",
            content="⚠️ **Error:** Session expired. Please restart the work order."
        ).send()
        return
    
    config = {"configurable": {"thread_id": thread_id}}
    
    log_to_terminal(f"Resuming graph execution for thread {thread_id}", "INFO")
    
    # Get current state from checkpoint
    try:
        state_snapshot = graph.get_state(config)
        current_state = state_snapshot.values
    except Exception as e:
        log_to_terminal(f"Error getting state: {e}", "ERROR")
        await cl.Message(
            author="System",
            content="⚠️ **Error:** Could not retrieve execution state. Please restart."
        ).send()
        return
    
    # Update state with human decision
    current_state["human_approval_context"] = {
        "recommendation": current_state.get("human_approval_context", {}).get("recommendation", ""),
        "recommendation_reason": current_state.get("human_approval_context", {}).get("recommendation_reason", ""),
        "awaiting_approval": False,
        "human_decision": decision,
        "human_notes": notes,
        "decision_timestamp": datetime.now().isoformat()
    }
    
    # Update work order status
    if decision == "APPROVED":
        current_state["work_completed"] = True
        current_state["verification_passed"] = True
        current_state["wo_closed"] = True
    else:
        current_state["work_completed"] = False
        current_state["verification_passed"] = False
        current_state["wo_closed"] = False
    
    # Update the checkpoint with new state
    graph.update_state(config, current_state)
    
    # Get work order info
    wo_id_full = wo_info.get("wo_id", wo_id)
    equipment = wo_info.get("equipment", "Unknown")
    wo_type = wo_info.get("wo_type", "Unknown")
    desc = wo_info.get("desc", "No description")
    
    log_to_terminal("Resuming graph from checkpoint", "INFO")
    
    # Resume execution - pass None to continue from checkpoint
    for chunk in graph.stream(None, config):
        node_name = list(chunk.keys())[0]
        state = chunk[node_name]
        
        log_to_terminal(f"Resumed node: {node_name}", "INFO")
        
        # Render outputs as nodes complete
        if node_name == "human_approval":
            await render_agent_output("human_approval", state, wo_id_full, equipment, wo_type, desc)
            await asyncio.sleep(0.5)
        elif node_name == "summary_agent":
            await render_agent_output("summary_agent", state, wo_id_full, equipment, wo_type, desc)
            await asyncio.sleep(0.5)
    
    # Show final summary
    await render_final_summary(state)
    
    log_to_terminal("Graph execution resumed and completed", "SUCCESS")
    
    # Signal completion and clean up
    await cl.Message(
        author="System", 
        content="✅ **Processing complete.** Ready for your next command."
    ).send()
    
    # Clean up session to release resources
    cl.user_session.set("processing", False)
    
    return  # Explicitly return to release Chainlit task



@cl.on_message
async def on_message(message: cl.Message):
    """Handle user messages"""
    user_input = message.content
    
    log_to_terminal(f"User message: {user_input}", "INFO")
    
    # STEP 1: Try data query handler first
    handled, response = await handle_data_query(user_input)
    
    if handled:
        # This was a data query - send the response
        log_to_terminal(f"Data query handled: {user_input}", "SUCCESS")
        await cl.Message(content=response).send()
        return
    
    # STEP 2: Check for execution command
    wo_match = re.search(r'\b(WO-[A-Z]+-\d+)\b', user_input, re.IGNORECASE)
    
    if wo_match and "execute" in user_input.lower():
        wo_id = wo_match.group(1).upper()
        
        log_to_terminal(f"Detected work order: {wo_id}", "SUCCESS")
        
        await process_single_work_order(wo_id, user_input)
    
    # else:
    #         await cl.Message(content="No work orders found in the system.").send()
    
    else:
        await cl.Message(
            content="""
I'd be happy to help! Here's what I can do:

**📋 Query Data:**
• `"What parts are needed for WO-PS-015?"` - Check required parts
• `"Show me details of WO-AC-006"` - Get work order information
• `"Check inventory for part PS-HF-004"` - Check stock levels
• `"Show all work orders"` - Browse available work orders
• `"What roles are available?"` - View maintenance roles
• `"Show schedule"` - View scheduled maintenance

**⚙️ Execute Work:**
• `"Execute WO-PS-015"` - Start full workflow execution

**Need help?** Just ask a question about work orders, parts, inventory, or roles!
"""
        ).send()
        
        log_to_terminal(f"Unclear query: {user_input}", "WARNING")