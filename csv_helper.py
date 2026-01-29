"""
csv_helper.py

CSV-backed data access layer for the Agentic Maintenance Planning Assistant.

Design goals
1. Keep business logic simple and deterministic
2. Provide small, well-scoped functions that are safe to expose as LLM tools
3. Make every function self-describing via clear docstrings, typed inputs, and predictable outputs

All functions operate on CSV files inside the data/ directory by default.
You can override the base directory by setting the environment variable DATA_DIR.

This module intentionally avoids any framework-specific code so it can be reused from
Chainlit, LangGraph, unit tests, or standalone scripts.
"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional


# ==============================
# Configuration
# ==============================

DATA_DIR = os.getenv("DATA_DIR", "data")

WORK_ORDERS_FILE = os.path.join(DATA_DIR, "work_orders.csv")
MAINTENANCE_SCHEDULE_FILE = os.path.join(DATA_DIR, "maintenance_schedule.csv")
MAINTENANCE_ROLES_FILE = os.path.join(DATA_DIR, "maintenance_roles.csv")
SPARE_PARTS_FILE = os.path.join(DATA_DIR, "spare_parts.csv")
WO_SPARE_REQUIREMENTS_FILE = os.path.join(DATA_DIR, "wo_spare_requirements.csv")
INVENTORY_FILE = os.path.join(DATA_DIR, "inventory.csv")
SPARE_ISSUES_FILE = os.path.join(DATA_DIR, "spare_issues.csv")
PURCHASE_REQUISITIONS_FILE = os.path.join(DATA_DIR, "purchase_requisitions.csv")

# Legacy file names (for backward compatibility if needed)
BOM_FILE = WO_SPARE_REQUIREMENTS_FILE  # Alias
MATERIAL_RESERVATIONS_FILE = SPARE_ISSUES_FILE  # Alias


# ==============================
# Errors
# ==============================

class CSVHelperError(RuntimeError):
    """Base exception for csv_helper related failures."""


class RecordNotFoundError(CSVHelperError):
    """Raised when a requested record does not exist."""


class InvalidDataError(CSVHelperError):
    """Raised when required fields are missing or data cannot be parsed."""


# ==============================
# Low level IO
# ==============================

def read_csv(file_path: str) -> List[Dict[str, str]]:
    """Read a CSV file into a list of dictionaries."""
    try:
        with open(file_path, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    except FileNotFoundError as e:
        raise CSVHelperError(f"CSV file not found: {file_path}") from e


def append_csv(file_path: str, row: Dict[str, Any], fieldnames: List[str]) -> None:
    """Append a single row to a CSV file."""
    try:
        with open(file_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writerow({k: row.get(k, "") for k in fieldnames})
    except FileNotFoundError as e:
        raise CSVHelperError(f"CSV file not found: {file_path}") from e


def _rewrite_csv(file_path: str, rows: List[Dict[str, Any]]) -> None:
    """Rewrite a CSV with the given rows preserving header order."""
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ==============================
# Work Orders
# ==============================

def get_work_order_by_id(work_order_id: str) -> Dict[str, str]:
    """Fetch a single work order row by work_order_id."""
    rows = read_csv(WORK_ORDERS_FILE)
    for row in rows:
        if row.get("work_order_id") == work_order_id:
            return row
    raise RecordNotFoundError(f"Work order not found: {work_order_id}")


# ==============================
# Maintenance Schedule
# ==============================

def _normalize_work_order_id(work_order_or_id: Any) -> str:
    """Normalize input to a work_order_id string.

    Accepts either:
    - work_order_id as str
    - work_order dict containing 'work_order_id'
    """
    if isinstance(work_order_or_id, str):
        return work_order_or_id

    if isinstance(work_order_or_id, dict):
        work_order_id = work_order_or_id.get("work_order_id")
        if work_order_id:
            return work_order_id

    raise InvalidDataError(
        f"Expected work_order_id (str) or work_order dict, got {type(work_order_or_id)}"
    )


def get_tasks_for_work_order(work_order_or_id: Any) -> List[Dict[str, str]]:
    """Return maintenance tasks for a given work order."""
    work_order_id = _normalize_work_order_id(work_order_or_id)

    rows = read_csv(MAINTENANCE_SCHEDULE_FILE)
    matched = [r for r in rows if r.get("work_order_id") == work_order_id]

    if matched:
        return matched

    return [{
        "work_order_id": work_order_id,
        "task_id": f"TASK-{work_order_id}",
        "description": "Scheduled maintenance task",
    }]


# ==============================
# Spare Parts (was Bill of Materials)
# ==============================

def get_required_parts_for_work_order(work_order_or_id: Any) -> List[Dict[str, Any]]:
    """Return required spare parts for a work order.

    This function:
    1. Resolves work_order_id (accepts str or work_order dict)
    2. Looks up spare requirements in wo_spare_requirements.csv
    3. Enriches with part details from spare_parts.csv

    Returns:
        List of dicts with:
        {
          "part_code": str,
          "part_name": str,
          "required_quantity": float,
          "equipment_code": str,
          "min_stock": int,
          "unit": str
        }
    """
    # Normalize input
    if isinstance(work_order_or_id, dict):
        work_order_id = work_order_or_id.get("work_order_id")
    else:
        work_order_id = work_order_or_id

    if not work_order_id or not isinstance(work_order_id, str):
        raise InvalidDataError("Valid work_order_id is required")

    # Read spare requirements
    requirements_rows = read_csv(WO_SPARE_REQUIREMENTS_FILE)
    spare_parts_rows = read_csv(SPARE_PARTS_FILE)
    
    # Create lookup for spare parts
    spare_lookup = {r.get("part_code"): r for r in spare_parts_rows if r.get("part_code")}
    
    required_parts: List[Dict[str, Any]] = []

    for row in requirements_rows:
        if row.get("work_order_id") != work_order_id:
            continue

        part_code = row.get("part_code")
        if not part_code:
            continue

        try:
            qty = float(row.get("required_quantity", 0))
        except (TypeError, ValueError) as e:
            raise InvalidDataError(
                f"Invalid required_quantity for part_code={part_code}"
            ) from e

        # Get part details
        spare_info = spare_lookup.get(part_code, {})
        
        required_parts.append({
            "part_code": part_code,
            "part_name": spare_info.get("part_name", "Unknown part"),
            "required_quantity": qty,
            "equipment_code": spare_info.get("equipment_code", ""),
            "unit": spare_info.get("unit", "pc"),
            "min_stock": int(spare_info.get("min_stock", 0)),
            # Legacy aliases for compatibility
            "part_id": part_code,
            "part_description": spare_info.get("part_name", "Unknown part"),
        })

    return required_parts


# ==============================
# Inventory
# ==============================

def check_inventory_for_parts(required_parts: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Check inventory availability for required spare parts."""
    inventory_rows = read_csv(INVENTORY_FILE)
    inventory_lookup = {
        r.get("part_code"): r for r in inventory_rows if r.get("part_code")
    }

    status: Dict[str, Dict[str, Any]] = {}

    for part in required_parts:
        # Support both part_code (new) and part_id (legacy)
        part_code = str(part.get("part_code") or part.get("part_id", ""))
        record = inventory_lookup.get(part_code)

        try:
            available_qty = float(record.get("quantity_available", 0)) if record else 0.0
        except (TypeError, ValueError):
            available_qty = 0.0

        status[part_code] = {
            "part_code": part_code,
            "available_quantity": available_qty,
            "location": record.get("store_location") if record else None,
            "sufficient": available_qty >= float(part.get("required_quantity", 0)),
            # Legacy aliases
            "part_id": part_code,
        }

    return status


# ==============================
# Spare Parts Issue (was Material Reservations)
# ==============================

def issue_spares_to_work_order(
    work_order_id: str,
    required_parts: List[Dict[str, Any]],
    inventory_status: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """Issue spare parts for a work order and update inventory.
    
    This function:
    1. Checks if parts are available
    2. Updates inventory quantities
    3. Logs issue transactions in spare_issues.csv
    
    Returns:
        Dict mapping part_code to issue status:
        {
          "part_code": {
            "status": "Issued" or "Not Available",
            "quantity_issued": float,
            "issue_id": str (if issued),
            "balance": float (remaining in inventory)
          }
        }
    """
    inventory_rows = read_csv(INVENTORY_FILE)
    inventory_lookup = {
        r.get("part_code"): r for r in inventory_rows if r.get("part_code")
    }

    issue_status: Dict[str, Dict[str, Any]] = {}
    inventory_updated = False

    for part in required_parts:
        # Support both part_code and part_id
        part_code = str(part.get("part_code") or part.get("part_id", ""))
        required_qty = float(part.get("required_quantity", 0))

        available_before = float(
            inventory_status.get(part_code, {}).get("available_quantity", 0)
        )

        if available_before >= required_qty and required_qty > 0:
            # Can issue
            available_after = available_before - required_qty
            status = "Issued"
            issued_qty = required_qty
            
            # Generate issue ID
            issue_id = f"ISS-{datetime.now().strftime('%Y%m%d%H%M%S')}"

            # Update inventory
            inv = inventory_lookup.get(part_code)
            if inv is not None:
                inv["quantity_available"] = str(available_after)
                inv["last_updated"] = datetime.now().strftime("%Y-%m-%d")  # Update timestamp
                inventory_updated = True
            
            # Log issue transaction
            append_csv(
                SPARE_ISSUES_FILE,
                {
                    "issue_id": issue_id,
                    "work_order_id": work_order_id,
                    "part_code": part_code,
                    "quantity_issued": issued_qty,
                    "issued_by": "SK",  # Storekeeper
                    "issued_date": datetime.now().strftime("%Y-%m-%d"),
                    "status": "Issued",
                },
                ["issue_id", "work_order_id", "part_code", "quantity_issued", 
                 "issued_by", "issued_date", "status"],
            )
        else:
            # Cannot issue
            available_after = available_before
            status = "Not Available"
            issued_qty = 0.0
            issue_id = None

        issue_status[part_code] = {
            "status": status,
            "quantity_issued": issued_qty,
            "issue_id": issue_id,
            "balance": available_after,
            "available_before": available_before,
            "available_after": available_after,
            # Legacy aliases
            "reserved_quantity": issued_qty,
            "part_id": part_code,
        }

    if inventory_updated:
        _rewrite_csv(INVENTORY_FILE, inventory_rows)

    return issue_status


# Legacy alias for backward compatibility
def reserve_materials(
    work_order_id: str,
    required_parts: List[Dict[str, Any]],
    inventory_status: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """Legacy function - calls issue_spares_to_work_order."""
    return issue_spares_to_work_order(work_order_id, required_parts, inventory_status)


# ==============================
# Purchase Requisitions
# ==============================

def create_purchase_requisitions(
    work_order_id: str,
    reservation_status: Dict[str, Dict[str, Any]],
    required_parts: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Create purchase requisitions for unavailable spare parts."""
    required_lookup = {
        str(p.get("part_code") or p.get("part_id")): float(p.get("required_quantity", 0))
        for p in required_parts
    }

    requests: List[Dict[str, Any]] = []

    for part_code, record in reservation_status.items():
        if record.get("status") != "Not Available":
            continue

        # Calculate shortage: required - available
        required_qty = required_lookup.get(part_code, 0.0)
        available_qty = record.get("available_before", 0.0)
        shortage_qty = max(required_qty - available_qty, 0.0)  # Can't be negative

        pr = {
            "pr_id": f"PR-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "part_code": part_code,
            "requested_qty": shortage_qty,  # ✅ FIXED: Order only the shortage
            "reason": f"Insufficient inventory (need {required_qty}, have {available_qty})",
            "linked_work_order": work_order_id,
            "status": "Open",
            "created_date": datetime.now().strftime("%Y-%m-%d"),
        }

        append_csv(
            PURCHASE_REQUISITIONS_FILE,
            pr,
            ["pr_id", "part_code", "requested_qty", "reason", "linked_work_order", "status", "created_date"],
        )

        requests.append(pr)

    return requests


# ==============================
# Role Management (NEW)
# ==============================

def get_role_for_work_order(work_order_id: str) -> str:
    """Get the primary role assigned to a work order (MMT/EMT/HT/OP)."""
    work_order = get_work_order_by_id(work_order_id)
    return work_order.get("primary_role", "MMT")


def get_all_roles() -> List[Dict[str, str]]:
    """Get all maintenance roles from maintenance_roles.csv."""
    return read_csv(MAINTENANCE_ROLES_FILE)


def get_role_details(role_code: str) -> Dict[str, str]:
    """Get details for a specific role (OP, MMT, EMT, HT, MS, SO, SK)."""
    roles = read_csv(MAINTENANCE_ROLES_FILE)
    for role in roles:
        if role.get("role_code") == role_code:
            return role
    raise RecordNotFoundError(f"Role not found: {role_code}")


# ==============================
# Work Order Queries (existing + enhanced)
# ==============================

def get_all_work_orders() -> List[Dict[str, str]]:
    """
    Fetch all work orders from the CSV.
    
    Returns:
        List of work order dictionaries
    """
    return read_csv(WORK_ORDERS_FILE)


def get_work_orders_by_filter(
    job_type: Optional[str] = None,
    equipment: Optional[str] = None
) -> List[Dict[str, str]]:
    """
    Fetch work orders matching specific criteria.
    
    Args:
        job_type: Filter by job type (Preventive/Corrective)
        equipment: Filter by equipment name
        
    Returns:
        List of matching work order dictionaries
    """
    rows = read_csv(WORK_ORDERS_FILE)
    
    if not job_type and not equipment:
        return rows
    
    filtered = []
    for row in rows:
        if job_type and row.get("job_type") != job_type:
            continue
        if equipment and row.get("equipment") != equipment:
            continue
        filtered.append(row)
    
    return filtered


def get_scheduled_work_orders(date: Optional[str] = None) -> List[Dict[str, str]]:
    """
    Get work orders scheduled for a specific date or all scheduled work orders.
    
    Args:
        date: Optional date string (YYYY-MM-DD format). If None, returns all.
        
    Returns:
        List of work order dictionaries with schedule info
    """
    schedule_rows = read_csv(MAINTENANCE_SCHEDULE_FILE)
    work_orders = read_csv(WORK_ORDERS_FILE)
    
    # Create lookup
    wo_lookup = {wo["work_order_id"]: wo for wo in work_orders}
    
    result = []
    for schedule in schedule_rows:
        if date and schedule.get("date") != date:
            continue
        
        wo_id = schedule.get("work_order_id")
        if wo_id in wo_lookup:
            wo_data = wo_lookup[wo_id].copy()
            wo_data["scheduled_date"] = schedule.get("date")
            result.append(wo_data)
    
    return result

# ==============================
# LLM tool support
# ==============================

@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: Dict[str, Any]


def get_tool_specs() -> List[ToolSpec]:
    """Return tool specifications for LLM tool calling."""
    return [
        ToolSpec(
            "get_work_order_by_id",
            "Fetch a work order by its ID.",
            {
                "type": "object",
                "properties": {
                    "work_order_id": {"type": "string"},
                },
                "required": ["work_order_id"],
            },
        ),
        ToolSpec(
            "get_all_work_orders",
            "Fetch all available work orders.",
            {
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        ToolSpec(
            "get_work_orders_by_filter",
            "Fetch work orders matching specific criteria like job type or equipment.",
            {
                "type": "object",
                "properties": {
                    "job_type": {"type": "string", "enum": ["Preventive", "Corrective", "Shutdown"]},
                    "equipment": {"type": "string"},
                },
                "required": [],
            },
        ),
        ToolSpec(
            "get_scheduled_work_orders",
            "Get work orders scheduled for a specific date or all scheduled work orders.",
            {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                },
                "required": [],
            },
        ),
        ToolSpec(
            "get_tasks_for_work_order",
            "Get maintenance tasks for a work order.",
            {
                "type": "object",
                "properties": {
                    "work_order_id": {"type": "string"},
                },
                "required": ["work_order_id"],
            },
        ),
        ToolSpec(
            "get_required_parts_for_work_order",
            "Get required spare parts for a work order.",
            {
                "type": "object",
                "properties": {
                    "work_order_id": {"type": "string"},
                },
                "required": ["work_order_id"],
            },
        ),
        ToolSpec(
            "check_inventory_for_parts",
            "Check inventory availability for required spare parts.",
            {
                "type": "object",
                "properties": {
                    "required_parts": {"type": "array", "items": {"type": "object"}},
                },
                "required": ["required_parts"],
            },
        ),
        ToolSpec(
            "issue_spares_to_work_order",
            "Issue spare parts for a work order and update inventory.",
            {
                "type": "object",
                "properties": {
                    "work_order_id": {"type": "string"},
                    "required_parts": {"type": "array", "items": {"type": "object"}},
                    "inventory_status": {"type": "object"},
                },
                "required": ["work_order_id", "required_parts", "inventory_status"],
            },
        ),
        ToolSpec(
            "reserve_materials",
            "Legacy alias for issue_spares_to_work_order.",
            {
                "type": "object",
                "properties": {
                    "work_order_id": {"type": "string"},
                    "required_parts": {"type": "array", "items": {"type": "object"}},
                    "inventory_status": {"type": "object"},
                },
                "required": ["work_order_id", "required_parts", "inventory_status"],
            },
        ),
        ToolSpec(
            "create_purchase_requisitions",
            "Create purchase requisitions for unavailable spare parts.",
            {
                "type": "object",
                "properties": {
                    "work_order_id": {"type": "string"},
                    "reservation_status": {"type": "object"},
                    "required_parts": {"type": "array", "items": {"type": "object"}},
                },
                "required": ["work_order_id", "reservation_status", "required_parts"],
            },
        ),
        ToolSpec(
            "get_role_for_work_order",
            "Get the primary role assigned to a work order (OP/MMT/EMT/HT).",
            {
                "type": "object",
                "properties": {
                    "work_order_id": {"type": "string"},
                },
                "required": ["work_order_id"],
            },
        ),
        ToolSpec(
            "get_all_roles",
            "Get all maintenance roles (OP, MMT, EMT, HT, MS, SO, SK).",
            {
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        ToolSpec(
            "get_role_details",
            "Get details for a specific role code.",
            {
                "type": "object",
                "properties": {
                    "role_code": {"type": "string", "enum": ["OP", "MMT", "EMT", "HT", "MS", "SO", "SK"]},
                },
                "required": ["role_code"],
            },
        ),
    ]

def get_tool_registry() -> Dict[str, Callable[..., Any]]:
    return {
        "get_work_order_by_id": get_work_order_by_id,
        "get_all_work_orders": get_all_work_orders,
        "get_work_orders_by_filter": get_work_orders_by_filter,
        "get_scheduled_work_orders": get_scheduled_work_orders,
        "get_tasks_for_work_order": get_tasks_for_work_order,
        "get_required_parts_for_work_order": get_required_parts_for_work_order,
        "check_inventory_for_parts": check_inventory_for_parts,
        "issue_spares_to_work_order": issue_spares_to_work_order,
        "reserve_materials": reserve_materials,  # Legacy alias
        "create_purchase_requisitions": create_purchase_requisitions,
        "get_role_for_work_order": get_role_for_work_order,
        "get_all_roles": get_all_roles,
        "get_role_details": get_role_details,
    }


def get_openai_tools_payload() -> List[Dict[str, Any]]:
    payload = []
    for spec in get_tool_specs():
        payload.append({
            "type": "function",
            "function": {
                "name": spec.name,
                "description": spec.description,
                "parameters": spec.parameters,
            },
        })
    return payload


def get_langchain_tools() -> List[Any]:
    try:
        from langchain_core.tools import StructuredTool
    except Exception as e:
        raise CSVHelperError(
            "LangChain is not available. Install langchain-core."
        ) from e

    tools = []
    for spec in get_tool_specs():
        tools.append(
            StructuredTool.from_function(
                func=get_tool_registry()[spec.name],
                name=spec.name,
                description=spec.description,
            )
        )
    return tools