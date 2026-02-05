"""
Database Tools
==============
LangChain @tool-decorated functions for database queries and mutations.
These tools are bound to agents that need database access (primarily Mira).
"""

import logging
from datetime import date, datetime
from typing import Optional

from langchain_core.tools import tool

from services.database import DatabaseService

logger = logging.getLogger(__name__)


# ============================================================
# Ticket Tools
# ============================================================


@tool
async def get_todays_tickets(due_date: Optional[str] = None) -> list[dict]:
    """Get all maintenance tickets due today or on a specific date.
    Args:
        due_date: Optional date in YYYY-MM-DD format. Defaults to today.
    """
    target_date = due_date or date.today().isoformat()
    rows = await DatabaseService.fetch_all(
        """
        SELECT mt.*, m.machine_code, m.name as machine_name, m.location,
               m.criticality, t.name as technician_name
        FROM maintenance_tickets mt
        JOIN machines m ON mt.machine_id = m.id
        LEFT JOIN technicians t ON mt.assigned_to_technician_id = t.id
        WHERE mt.due_date = %s AND mt.status NOT IN ('completed', 'closed')
        ORDER BY
            CASE mt.priority
                WHEN 'critical' THEN 1
                WHEN 'high' THEN 2
                WHEN 'medium' THEN 3
                WHEN 'low' THEN 4
            END,
            mt.created_at
        """,
        (target_date,),
    )
    return rows


@tool
async def get_tickets_by_status(status: str) -> list[dict]:
    """Get all maintenance tickets with a specific status.
    Args:
        status: Ticket status - one of: open, assigned, in_progress, waiting_parts, completed, closed
    """
    rows = await DatabaseService.fetch_all(
        """
        SELECT mt.*, m.machine_code, m.name as machine_name, m.location, m.criticality
        FROM maintenance_tickets mt
        JOIN machines m ON mt.machine_id = m.id
        WHERE mt.status = %s
        ORDER BY mt.priority DESC, mt.due_date
        """,
        (status,),
    )
    return rows


@tool
async def get_ticket_by_number(ticket_number: str) -> Optional[dict]:
    """Get a specific ticket by its ticket number (e.g., CM-2026-0001).
    Args:
        ticket_number: The ticket number to look up.
    """
    return await DatabaseService.fetch_one(
        """
        SELECT mt.*, m.machine_code, m.name as machine_name, m.location,
               m.criticality, t.name as technician_name
        FROM maintenance_tickets mt
        JOIN machines m ON mt.machine_id = m.id
        LEFT JOIN technicians t ON mt.assigned_to_technician_id = t.id
        WHERE mt.ticket_number = %s
        """,
        (ticket_number,),
    )


@tool
async def get_ticket_counts() -> dict:
    """Get counts of tickets by type and status."""
    rows = await DatabaseService.fetch_all(
        """
        SELECT ticket_type, status, COUNT(*) as count
        FROM maintenance_tickets
        WHERE status NOT IN ('closed')
        GROUP BY ticket_type, status
        ORDER BY ticket_type, status
        """
    )
    result = {"CM": {}, "PM": {}, "total": 0}
    for row in rows:
        result[row["ticket_type"]][row["status"]] = row["count"]
        result["total"] += row["count"]
    return result


@tool
async def update_ticket_status(
    ticket_id: int, new_status: str, notes: Optional[str] = None
) -> dict:
    """Update the status of a maintenance ticket.
    Args:
        ticket_id: The ticket ID to update.
        new_status: New status - one of: open, assigned, in_progress, waiting_parts, completed, closed
        notes: Optional notes to append.
    """
    completed_at = "NOW()" if new_status in ("completed", "closed") else "NULL"
    row = await DatabaseService.execute_returning(
        f"""
        UPDATE maintenance_tickets
        SET status = %s,
            notes = COALESCE(notes || E'\\n', '') || COALESCE(%s, ''),
            completed_at = {completed_at if new_status in ('completed', 'closed') else 'completed_at'},
            updated_at = NOW()
        WHERE id = %s
        RETURNING *
        """,
        (new_status, notes, ticket_id),
    )
    return row or {"error": "Ticket not found"}


# ============================================================
# Machine Tools
# ============================================================


@tool
async def get_machine_info(machine_code: str) -> Optional[dict]:
    """Get detailed information about a machine by its code (e.g., MIX-001).
    Args:
        machine_code: The machine code to look up.
    """
    return await DatabaseService.fetch_one(
        """
        SELECT m.*, i.name as industry_name
        FROM machines m
        JOIN industries i ON m.industry_id = i.id
        WHERE m.machine_code = %s
        """,
        (machine_code,),
    )


@tool
async def get_all_machines() -> list[dict]:
    """Get all machines with their industry and status."""
    return await DatabaseService.fetch_all(
        """
        SELECT m.*, i.name as industry_name
        FROM machines m
        JOIN industries i ON m.industry_id = i.id
        ORDER BY m.criticality DESC, m.machine_code
        """
    )


# ============================================================
# BOM (Bill of Materials) Tools
# ============================================================


@tool
async def get_bom_for_machine(machine_id: int) -> list[dict]:
    """Get the Bill of Materials (all required parts) for a machine.
    Args:
        machine_id: The machine ID to get BOM for.
    """
    return await DatabaseService.fetch_all(
        """
        SELECT b.*, p.part_number, p.name as part_name, p.category,
               p.unit_cost, p.unit_of_measure,
               COALESCE(inv.quantity_on_hand, 0) as stock_on_hand,
               inv.bin_location
        FROM bom b
        JOIN parts_catalog p ON b.part_id = p.id
        LEFT JOIN inventory inv ON p.id = inv.part_id
        WHERE b.machine_id = %s
        ORDER BY b.is_critical DESC, p.category
        """,
        (machine_id,),
    )


@tool
async def check_part_in_bom(machine_id: int, part_id: int) -> dict:
    """Check if a specific part is in the BOM for a machine.
    Args:
        machine_id: The machine ID.
        part_id: The part ID to check.
    """
    row = await DatabaseService.fetch_one(
        """
        SELECT b.*, p.part_number, p.name as part_name, m.machine_code, m.name as machine_name
        FROM bom b
        JOIN parts_catalog p ON b.part_id = p.id
        JOIN machines m ON b.machine_id = m.id
        WHERE b.machine_id = %s AND b.part_id = %s
        """,
        (machine_id, part_id),
    )
    if row:
        return {"in_bom": True, **row}
    else:
        # Get part and machine names for the warning message
        part = await DatabaseService.fetch_one(
            "SELECT part_number, name FROM parts_catalog WHERE id = %s", (part_id,)
        )
        machine = await DatabaseService.fetch_one(
            "SELECT machine_code, name FROM machines WHERE id = %s", (machine_id,)
        )
        return {
            "in_bom": False,
            "part_number": part["part_number"] if part else "unknown",
            "part_name": part["name"] if part else "unknown",
            "machine_code": machine["machine_code"] if machine else "unknown",
            "machine_name": machine["name"] if machine else "unknown",
        }


# ============================================================
# Inventory Tools
# ============================================================


@tool
async def check_inventory(part_id: int) -> Optional[dict]:
    """Check inventory level for a specific part.
    Args:
        part_id: The part ID to check inventory for.
    """
    return await DatabaseService.fetch_one(
        """
        SELECT inv.*, p.part_number, p.name as part_name, p.category
        FROM inventory inv
        JOIN parts_catalog p ON inv.part_id = p.id
        WHERE inv.part_id = %s
        """,
        (part_id,),
    )


@tool
async def check_inventory_by_part_number(part_number: str) -> Optional[dict]:
    """Check inventory level for a part by its part number.
    Args:
        part_number: The part number (e.g., BRG-6205-2RS).
    """
    return await DatabaseService.fetch_one(
        """
        SELECT inv.*, p.part_number, p.name as part_name, p.category
        FROM inventory inv
        JOIN parts_catalog p ON inv.part_id = p.id
        WHERE p.part_number = %s
        """,
        (part_number,),
    )


@tool
async def get_low_stock_parts() -> list[dict]:
    """Get all parts that are at or below their reorder level."""
    return await DatabaseService.fetch_all(
        """
        SELECT inv.*, p.part_number, p.name as part_name, p.category, p.unit_cost
        FROM inventory inv
        JOIN parts_catalog p ON inv.part_id = p.id
        WHERE inv.quantity_on_hand <= inv.reorder_level
        ORDER BY inv.quantity_on_hand ASC
        """
    )


@tool
async def get_full_inventory() -> list[dict]:
    """Get complete inventory listing with all parts and stock levels."""
    return await DatabaseService.fetch_all(
        """
        SELECT inv.*, p.part_number, p.name as part_name, p.category,
               p.unit_cost, p.unit_of_measure,
               CASE
                   WHEN inv.quantity_on_hand = 0 THEN 'OUT_OF_STOCK'
                   WHEN inv.quantity_on_hand <= inv.reorder_level THEN 'LOW_STOCK'
                   ELSE 'IN_STOCK'
               END as stock_status
        FROM inventory inv
        JOIN parts_catalog p ON inv.part_id = p.id
        ORDER BY
            CASE
                WHEN inv.quantity_on_hand = 0 THEN 1
                WHEN inv.quantity_on_hand <= inv.reorder_level THEN 2
                ELSE 3
            END,
            p.category, p.part_number
        """
    )


@tool
async def update_inventory(
    part_id: int, quantity_change: int, reason: str = ""
) -> dict:
    """Update inventory quantity for a part (positive to add, negative to deduct).
    Args:
        part_id: The part ID to update.
        quantity_change: Amount to add (positive) or deduct (negative).
        reason: Reason for the change (e.g., "Issued for WO-2026-0001").
    """
    row = await DatabaseService.execute_returning(
        """
        UPDATE inventory
        SET quantity_on_hand = GREATEST(quantity_on_hand + %s, 0),
            updated_at = NOW()
        WHERE part_id = %s
        RETURNING *, (SELECT part_number FROM parts_catalog WHERE id = %s) as part_number
        """,
        (quantity_change, part_id, part_id),
    )
    return row or {"error": "Part not found in inventory"}


# ============================================================
# Technician Tools
# ============================================================


@tool
async def get_available_technicians(
    specialization: Optional[str] = None,
) -> list[dict]:
    """Get available technicians, optionally filtered by specialization.
    Args:
        specialization: Optional filter for specialization (e.g., Mechanical, Electrical).
    """
    if specialization:
        return await DatabaseService.fetch_all(
            """
            SELECT * FROM technicians
            WHERE is_available = TRUE AND LOWER(specialization) LIKE LOWER(%s)
            ORDER BY name
            """,
            (f"%{specialization}%",),
        )
    return await DatabaseService.fetch_all(
        "SELECT * FROM technicians WHERE is_available = TRUE ORDER BY name"
    )


# ============================================================
# Work Order Tools
# ============================================================


@tool
async def create_work_order(
    ticket_id: int,
    technician_id: int,
    description: str,
    procedures: str,
    scheduled_date: str,
    estimated_hours: float = 2.0,
) -> dict:
    """Create a new work order for a maintenance ticket.
    Args:
        ticket_id: The maintenance ticket ID.
        technician_id: The assigned technician ID.
        description: Work description.
        procedures: Step-by-step procedures.
        scheduled_date: Scheduled date in YYYY-MM-DD format.
        estimated_hours: Estimated hours for the work.
    """
    # Generate work order number
    count_row = await DatabaseService.fetch_one(
        "SELECT COUNT(*) + 1 as next_num FROM work_orders"
    )
    wo_number = f"WO-2026-{count_row['next_num']:04d}"

    row = await DatabaseService.execute_returning(
        """
        INSERT INTO work_orders
            (work_order_number, ticket_id, technician_id, description,
             procedures, status, estimated_hours, scheduled_date)
        VALUES (%s, %s, %s, %s, %s, 'assigned', %s, %s)
        RETURNING *
        """,
        (
            wo_number,
            ticket_id,
            technician_id,
            description,
            procedures,
            estimated_hours,
            scheduled_date,
        ),
    )

    # Update ticket status to assigned
    await DatabaseService.execute(
        """
        UPDATE maintenance_tickets
        SET status = 'assigned', assigned_to_technician_id = %s, updated_at = NOW()
        WHERE id = %s
        """,
        (technician_id, ticket_id),
    )

    return row


@tool
async def add_work_order_parts(
    work_order_id: int, parts: list[dict]
) -> list[dict]:
    """Add required parts to a work order.
    Args:
        work_order_id: The work order ID.
        parts: List of dicts with part_id, quantity_required, is_correct_for_machine.
    """
    results = []
    for part in parts:
        row = await DatabaseService.execute_returning(
            """
            INSERT INTO work_order_parts
                (work_order_id, part_id, quantity_required, is_correct_for_machine)
            VALUES (%s, %s, %s, %s)
            RETURNING *
            """,
            (
                work_order_id,
                part["part_id"],
                part["quantity_required"],
                part.get("is_correct_for_machine", True),
            ),
        )
        results.append(row)
    return results


@tool
async def update_work_order_status(
    work_order_id: int,
    new_status: str,
    technician_notes: Optional[str] = None,
) -> dict:
    """Update work order status.
    Args:
        work_order_id: The work order ID.
        new_status: New status - one of: pending, assigned, in_progress, waiting_parts, completed, cancelled
        technician_notes: Optional notes from the technician.
    """
    started = ", started_at = NOW()" if new_status == "in_progress" else ""
    completed = ", completed_at = NOW()" if new_status in ("completed", "cancelled") else ""

    row = await DatabaseService.execute_returning(
        f"""
        UPDATE work_orders
        SET status = %s,
            technician_notes = COALESCE(technician_notes || E'\\n', '') || COALESCE(%s, '')
            {started}{completed},
            updated_at = NOW()
        WHERE id = %s
        RETURNING *
        """,
        (new_status, technician_notes, work_order_id),
    )
    return row or {"error": "Work order not found"}


@tool
async def get_work_order_details(work_order_id: int) -> Optional[dict]:
    """Get full details of a work order including ticket, machine, technician, and parts.
    Args:
        work_order_id: The work order ID.
    """
    wo = await DatabaseService.fetch_one(
        """
        SELECT wo.*, mt.ticket_number, mt.ticket_type, mt.title as ticket_title,
               mt.priority, m.machine_code, m.name as machine_name, m.location,
               t.name as technician_name, t.specialization
        FROM work_orders wo
        JOIN maintenance_tickets mt ON wo.ticket_id = mt.id
        JOIN machines m ON mt.machine_id = m.id
        LEFT JOIN technicians t ON wo.technician_id = t.id
        WHERE wo.id = %s
        """,
        (work_order_id,),
    )
    if wo:
        parts = await DatabaseService.fetch_all(
            """
            SELECT wop.*, p.part_number, p.name as part_name, p.category,
                   COALESCE(inv.quantity_on_hand, 0) as stock_on_hand,
                   inv.bin_location
            FROM work_order_parts wop
            JOIN parts_catalog p ON wop.part_id = p.id
            LEFT JOIN inventory inv ON p.id = inv.part_id
            WHERE wop.work_order_id = %s
            ORDER BY p.category
            """,
            (work_order_id,),
        )
        wo["parts"] = parts
    return wo


# ============================================================
# Vendor & Procurement Tools
# ============================================================


@tool
async def get_vendors_by_priority() -> list[dict]:
    """Get all active vendors ordered by priority rank (1 = primary)."""
    return await DatabaseService.fetch_all(
        """
        SELECT * FROM vendors
        WHERE status = 'active'
        ORDER BY priority_rank
        """
    )


@tool
async def create_purchase_requisition(
    work_order_id: int,
    part_id: int,
    quantity: int,
    vendor_id: int,
) -> dict:
    """Create a purchase requisition for an out-of-stock part.
    Args:
        work_order_id: The work order needing the part.
        part_id: The part to order.
        quantity: Quantity to order.
        vendor_id: The vendor to order from.
    """
    count_row = await DatabaseService.fetch_one(
        "SELECT COUNT(*) + 1 as next_num FROM purchase_requisitions"
    )
    pr_number = f"PR-2026-{count_row['next_num']:04d}"

    row = await DatabaseService.execute_returning(
        """
        INSERT INTO purchase_requisitions
            (requisition_number, work_order_id, part_id, quantity, vendor_id, status)
        VALUES (%s, %s, %s, %s, %s, 'requested')
        RETURNING *
        """,
        (pr_number, work_order_id, part_id, quantity, vendor_id),
    )
    return row


@tool
async def update_purchase_requisition(
    requisition_id: int,
    status: Optional[str] = None,
    vendor_id: Optional[int] = None,
    quoted_price: Optional[float] = None,
    expected_delivery: Optional[str] = None,
    vendor_response: Optional[str] = None,
) -> dict:
    """Update a purchase requisition with vendor response details.
    Args:
        requisition_id: The requisition ID to update.
        status: New status - one of: requested, quoted, ordered, delivered, cancelled
        vendor_id: Updated vendor ID (if switching vendors).
        quoted_price: Vendor's quoted price.
        expected_delivery: Expected delivery date (YYYY-MM-DD).
        vendor_response: Raw vendor response text.
    """
    updates = []
    params = []

    if status:
        updates.append("status = %s")
        params.append(status)
    if vendor_id is not None:
        updates.append("vendor_id = %s")
        params.append(vendor_id)
    if quoted_price is not None:
        updates.append("quoted_price = %s")
        params.append(quoted_price)
    if expected_delivery:
        updates.append("expected_delivery = %s")
        params.append(expected_delivery)
    if vendor_response:
        updates.append("vendor_response = %s")
        params.append(vendor_response)

    updates.append("updated_at = NOW()")
    params.append(requisition_id)

    row = await DatabaseService.execute_returning(
        f"""
        UPDATE purchase_requisitions
        SET {', '.join(updates)}
        WHERE id = %s
        RETURNING *
        """,
        tuple(params),
    )
    return row or {"error": "Requisition not found"}


@tool
async def search_parts(search_term: str) -> list[dict]:
    """Search for parts by name, number, or category.
    Args:
        search_term: Search term to match against part number, name, or category.
    """
    return await DatabaseService.fetch_all(
        """
        SELECT p.*, COALESCE(inv.quantity_on_hand, 0) as stock_on_hand,
               inv.bin_location
        FROM parts_catalog p
        LEFT JOIN inventory inv ON p.id = inv.part_id
        WHERE LOWER(p.part_number) LIKE LOWER(%s)
           OR LOWER(p.name) LIKE LOWER(%s)
           OR LOWER(p.category) LIKE LOWER(%s)
        ORDER BY p.category, p.part_number
        """,
        (f"%{search_term}%", f"%{search_term}%", f"%{search_term}%"),
    )
