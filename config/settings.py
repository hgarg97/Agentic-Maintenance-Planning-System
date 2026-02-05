"""
ONE-STOP-SHOP Configuration File
================================
All hardcoded values, agent configurations, model settings, database config,
email config, vendor config, and UI config live here.

To change ANY agent name, role, avatar, model, or system behavior,
edit ONLY this file.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# Agent Configuration
# ============================================================

AGENTS = {
    "james": {
        "name": "James",
        "role": "Maintenance Planner",
        "title": "Agent James - Maintenance Planner",
        "avatar": "public/avatars/james.jpg",
        "model": "gpt-4o",
        "description": "Supervisor and orchestrator of the maintenance planning system",
        "color": "#1E90FF",
    },
    "david": {
        "name": "David",
        "role": "Maintenance Supervisor",
        "title": "Agent David - Maintenance Supervisor",
        "avatar": "public/avatars/david.jpg",
        "model": "gpt-4o",
        "description": "Manages work orders and assigns technicians",
        "color": "#32CD32",
    },
    "mira": {
        "name": "Mira",
        "role": "Inventory Manager",
        "title": "Agent Mira - Inventory Manager",
        "avatar": "public/avatars/mira.jpg",
        "model": "gpt-4o",
        "description": "Manages inventory, checks parts availability, validates BOM",
        "color": "#FFD700",
    },
    "roberto": {
        "name": "Roberto",
        "role": "Procurement Agent",
        "title": "Agent Roberto - Procurement Agent",
        "avatar": "public/avatars/robert.jpg",
        "model": "gpt-4o",
        "description": "Handles vendor communication and parts procurement",
        "color": "#DC143C",
    },
    "technician": {
        "name": "Technician",
        "role": "Human Technician",
        "title": "Human Technician",
        "avatar": "public/avatars/human-in-loop.jpg",
        "model": None,  # Human - no LLM
        "description": "Human-in-the-loop technician performing maintenance work",
        "color": "#9370DB",
    },
    "system": {
        "name": "System",
        "role": "System",
        "title": "Maintenance Planning System",
        "avatar": "public/avatars/system.jpg",
        "model": None,
        "description": "System notifications and status updates",
        "color": "#4DA6FF",
    },
}

# ============================================================
# Model Configuration
# ============================================================

MODELS = {
    "main": "gpt-4o",               # For agent reasoning and decision-making
    "lightweight": "gpt-4o-mini",    # For classification, rephrasing, email parsing
    "temperature": 0.1,              # Low temperature for deterministic outputs
    "temperature_creative": 0.4,     # Slightly higher for summary generation
    "max_tokens": 4096,              # Max tokens per response
    "max_tokens_classify": 256,      # Max tokens for classification tasks
}

# ============================================================
# Database Configuration
# ============================================================

DATABASE = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "name": os.getenv("DB_NAME", "maintenance_db"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
    "min_connections": 2,
    "max_connections": 10,
}

def get_database_url() -> str:
    """Build PostgreSQL connection URL from config."""
    return (
        f"postgresql://{DATABASE['user']}:{DATABASE['password']}"
        f"@{DATABASE['host']}:{DATABASE['port']}/{DATABASE['name']}"
    )

# ============================================================
# Email Configuration
# ============================================================

EMAIL = {
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "imap_server": "imap.gmail.com",
    "imap_port": 993,
    "sender_email": os.getenv("GMAIL_USER", ""),
    "sender_password": os.getenv("GMAIL_APP_PASSWORD", ""),
    "sender_name": "Maintenance Planning System",
    "poll_interval_seconds": 30,
    "poll_timeout_minutes": 10,
}

# ============================================================
# Vendor Configuration
# ============================================================

VENDORS = {
    "vendor_a": {
        "code": "VEND-A",
        "name": "Alpha Industrial Supplies",
        "email": os.getenv("VENDOR_A_EMAIL", "vendor.a@example.com"),
        "priority": 1,  # Primary vendor (contacted first)
    },
    "vendor_b": {
        "code": "VEND-B",
        "name": "Beta Parts Corporation",
        "email": os.getenv("VENDOR_B_EMAIL", "vendor.b@example.com"),
        "priority": 2,  # Fallback vendor
    },
}

# ============================================================
# Ticket & Work Order Numbering
# ============================================================

PREFIXES = {
    "cm_ticket": "CM",
    "pm_ticket": "PM",
    "work_order": "WO",
    "purchase_requisition": "PR",
}

# ============================================================
# User Intent Classification Categories
# ============================================================

INTENT_CATEGORIES = [
    "execute_maintenance",     # User wants to run maintenance tasks for the day
    "execute_single_ticket",   # User wants to execute a specific ticket
    "inventory_query",         # User wants inventory/stock information
    "ticket_query",            # User wants ticket/status information
    "priority_query",          # User wants to know what to prioritize
    "email_report",            # User wants a summary emailed
    "general_qa",              # General question about maintenance
]

# ============================================================
# UI Configuration
# ============================================================

UI = {
    "app_title": "Agentic Maintenance Planning System",
    "app_description": "AI-Powered Maintenance Operations Center",
    "streaming_delay_ms": 15,
    "welcome_message": (
        "Welcome to the **Agentic Maintenance Planning System**.\n\n"
        "I'm **James**, your Maintenance Planner. I coordinate with my team to help you "
        "manage all maintenance operations efficiently.\n\n"
        "**My Team:**\n"
        "- **David** - Maintenance Supervisor (work orders & technician assignments)\n"
        "- **Mira** - Inventory Manager (parts, stock levels & database queries)\n"
        "- **Roberto** - Procurement Agent (vendor communication & parts ordering)\n\n"
        "**What can I help you with?**\n"
        "- View today's maintenance schedule\n"
        "- Execute daily maintenance tasks\n"
        "- Check inventory and parts availability\n"
        "- Get priority recommendations\n"
        "- Generate status reports\n\n"
        "Just type your request and I'll take care of the rest!"
    ),
}

# ============================================================
# Industry Configuration (for scalability)
# ============================================================

INDUSTRIES = {
    "rubber": {
        "code": "RUBBER",
        "name": "Rubber Manufacturing",
        "description": "Rubber processing and manufacturing operations",
    },
    "oil_gas": {
        "code": "OIL_GAS",
        "name": "Oil & Gas",
        "description": "Oil and gas exploration and production operations",
    },
    "aerospace": {
        "code": "AEROSPACE",
        "name": "Aerospace",
        "description": "Aerospace manufacturing and MRO operations",
    },
    "manufacturing": {
        "code": "MFG",
        "name": "General Manufacturing",
        "description": "General manufacturing and production operations",
    },
}
