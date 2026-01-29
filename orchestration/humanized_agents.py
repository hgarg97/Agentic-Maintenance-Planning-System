# Humanized Agent Responses - Making AI agents sound like real maintenance workers

"""
This module contains helper functions to make agent responses more human and conversational.
Instead of formal reports, agents will communicate like real people in a maintenance team.
"""

import random
from typing import Dict, List

# =========================
# Human-like response templates
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

ROBERT_GREETINGS = [
    "Alright, let me do my safety check.",
    "Time for the safety verification.",
    "Let's make sure everything's safe here.",
    "Running through my safety checklist now.",
]

ROBERT_APPROVAL = [
    "Everything checks out. Looking good!",
    "All safety requirements met. Nice work!",
    "Passed inspection. You're clear to close this.",
    "Safety verified. Job well done!",
]

JAMES_GREETINGS = [
    "Alright, let me recap what just happened here.",
    "Okay everyone, here's how this all went down.",
    "Let me summarize this whole work order for you.",
    "Here's the complete picture of what we did today.",
]


# =========================
# Humanized message builders
# =========================

def sarah_issue_report(wo_id: str, equipment: str, issue_desc: str, severity: str, wo_type: str) -> str:
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


def david_assignment_message(tech_name: str, tech_role: str, equipment: str, wo_id: str, 
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


def tech_planning_message(tech_name: str, tech_role: str, wo_id: str, equipment: str, 
                          desc: str, parts_count: int) -> str:
    """Technician's conversational work planning"""
    
    # Different greetings based on role
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


def tech_parts_request(tech_name: str, parts: List[Dict]) -> str:
    """Technician's casual parts request to Mira"""
    
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
        
        # Make quantity more casual
        qty_text = f"{int(qty)} piece" if qty == 1 else f"{int(qty)} pieces"
        parts_list.append(f"• **{part_code}** - {part_name} ({qty_text})")
    
    return f"""
### 🔧 **Parts Request**

{intro}

{chr(10).join(parts_list)}

Let me know if you have them in stock!
"""


def mira_parts_response(parts_available: List[str], parts_unavailable: List[str], 
                         issued_count: int) -> str:
    """Mira's conversational parts response"""
    
    greeting = random.choice(MIRA_GREETINGS)
    
    if not parts_unavailable:
        good_news = random.choice(MIRA_GOOD_NEWS)
        return f"""
{greeting}

{good_news}

✅ **Issued {issued_count} item(s)** - Parts are ready for pickup at the maintenance store.

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


def robert_safety_approval(wo_id: str, tech_name: str, loto_required: bool) -> str:
    """Robert's conversational safety approval"""
    
    greeting = random.choice(ROBERT_GREETINGS)
    approval = random.choice(ROBERT_APPROVAL)
    
    loto_note = ""
    if loto_required:
        loto_note = f"\n\n✅ LOTO was done correctly with {tech_name} - no shortcuts, no issues."
    
    return f"""
{greeting}

**Work Order {wo_id}** - Final Safety Check

{approval}

Here's what I verified:
• ✅ All safety procedures followed
• ✅ Equipment tested and working normally
• ✅ Guards and covers properly installed
• ✅ Work area cleaned up
• ✅ No safety hazards{loto_note}

**This work order is APPROVED and CLOSED.** 

Good job, {tech_name}! Equipment is safe to operate.

Next inspection scheduled for 3 months from now.
"""


def james_casual_summary(wo_id: str, equipment: str, wo_type: str, execution_summary: Dict) -> str:
    """James's conversational summary"""
    
    greeting = random.choice(JAMES_GREETINGS)
    
    # Extract info
    tech_name = execution_summary.get('tech_name', 'the technician')
    parts_count = execution_summary.get('parts_count', 0)
    duration = execution_summary.get('duration', 'a few hours')
    status = execution_summary.get('status', 'completed')
    
    # Status emoji and message
    if status == 'closed':
        status_msg = "✅ **All done and closed!**"
        conclusion = f"The {equipment} is back up and running. {tech_name} did a solid job on this one."
    elif status == 'blocked':
        status_msg = "⏸️ **On hold for now**"
        conclusion = f"We're waiting on parts to arrive. I'll update everyone when we can continue."
    else:
        status_msg = "🔄 **Still in progress**"
        conclusion = f"Work is ongoing. I'll keep everyone posted."
    
    return f"""
{greeting}

# 📋 **Work Order {wo_id} - {equipment}**

{status_msg}

**What Happened:**

**Sarah** spotted the issue during her rounds and flagged it
↓
**David** reviewed it and assigned {tech_name} to handle it
↓
**{tech_name}** planned the work and requested {parts_count} part(s)
↓
**Mira** checked inventory and issued the parts
↓
**Robert** did the final safety check and approved closure

---

{conclusion}

That's a wrap for {wo_id}!
"""


# =========================
# Integration helper
# =========================

def get_human_message(agent_type: str, context: Dict) -> str:
    """
    Get a humanized message for any agent type.
    
    Args:
        agent_type: 'sarah', 'david', 'tech', 'mira', 'robert', 'james'
        context: Dictionary with relevant context for that agent
    
    Returns:
        Human-like message string
    """
    
    if agent_type == 'sarah':
        return sarah_issue_report(
            wo_id=context.get('wo_id', 'Unknown'),
            equipment=context.get('equipment', 'Equipment'),
            issue_desc=context.get('issue_desc', 'Issue detected'),
            severity=context.get('severity', 'Medium'),
            wo_type=context.get('wo_type', 'Maintenance')
        )
    
    elif agent_type == 'david':
        return david_assignment_message(
            tech_name=context.get('tech_name', 'Technician'),
            tech_role=context.get('tech_role', 'MMT'),
            equipment=context.get('equipment', 'Equipment'),
            wo_id=context.get('wo_id', 'Unknown'),
            requires_loto=context.get('requires_loto', False),
            safety_critical=context.get('safety_critical', False)
        )
    
    elif agent_type == 'tech_planning':
        return tech_planning_message(
            tech_name=context.get('tech_name', 'Technician'),
            tech_role=context.get('tech_role', 'MMT'),
            wo_id=context.get('wo_id', 'Unknown'),
            equipment=context.get('equipment', 'Equipment'),
            desc=context.get('description', 'Work required'),
            parts_count=context.get('parts_count', 0)
        )
    
    elif agent_type == 'tech_parts':
        return tech_parts_request(
            tech_name=context.get('tech_name', 'Technician'),
            parts=context.get('parts', [])
        )
    
    elif agent_type == 'mira':
        return mira_parts_response(
            parts_available=context.get('parts_available', []),
            parts_unavailable=context.get('parts_unavailable', []),
            issued_count=context.get('issued_count', 0)
        )
    
    elif agent_type == 'robert':
        return robert_safety_approval(
            wo_id=context.get('wo_id', 'Unknown'),
            tech_name=context.get('tech_name', 'Technician'),
            loto_required=context.get('loto_required', False)
        )
    
    elif agent_type == 'james':
        return james_casual_summary(
            wo_id=context.get('wo_id', 'Unknown'),
            equipment=context.get('equipment', 'Equipment'),
            wo_type=context.get('wo_type', 'Maintenance'),
            execution_summary=context.get('execution_summary', {})
        )
    
    return "Message formatting error"
