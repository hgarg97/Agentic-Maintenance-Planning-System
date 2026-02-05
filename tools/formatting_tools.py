"""
Formatting Tools
================
Markdown card builders and formatters for rich Chainlit display.
Generates work order cards, inventory tables, ticket summaries, etc.
"""

from datetime import date


def format_work_order_card(work_order: dict) -> str:
    """Build a rich markdown work order card for display."""
    status_icon = {
        "pending": "🟡",
        "assigned": "🔵",
        "in_progress": "🟠",
        "waiting_parts": "🔴",
        "completed": "🟢",
        "cancelled": "⚫",
    }.get(work_order.get("status", ""), "⚪")

    priority_icon = {
        "critical": "🔴",
        "high": "🟠",
        "medium": "🟡",
        "low": "🟢",
    }.get(work_order.get("priority", ""), "⚪")

    card = f"""### Work Order: {work_order.get('work_order_number', 'N/A')}

| Field | Details |
|-------|---------|
| **Ticket** | {work_order.get('ticket_number', 'N/A')} ({work_order.get('ticket_type', '')}) |
| **Machine** | {work_order.get('machine_name', 'N/A')} ({work_order.get('machine_code', '')}) |
| **Location** | {work_order.get('location', 'N/A')} |
| **Priority** | {priority_icon} {work_order.get('priority', 'N/A').upper()} |
| **Status** | {status_icon} {work_order.get('status', 'N/A').replace('_', ' ').title()} |
| **Technician** | {work_order.get('technician_name', 'Unassigned')} |
| **Scheduled** | {work_order.get('scheduled_date', 'N/A')} |
| **Est. Hours** | {work_order.get('estimated_hours', 'N/A')} |

**Description:**
{work_order.get('description', 'No description provided.')}
"""

    # Add parts table if parts exist
    parts = work_order.get("parts", [])
    if parts:
        card += "\n**Required Parts:**\n\n"
        card += "| Part # | Part Name | Qty Needed | In Stock | Bin | Status |\n"
        card += "|--------|-----------|-----------|----------|-----|--------|\n"
        for p in parts:
            stock = p.get("stock_on_hand", 0)
            needed = p.get("quantity_required", 0)
            available = "Available" if stock >= needed else "**OUT OF STOCK**" if stock == 0 else f"Low ({stock})"
            bom_match = "" if p.get("is_correct_for_machine", True) else " ⚠️"
            card += (
                f"| {p.get('part_number', '')} | {p.get('part_name', '')}{bom_match} "
                f"| {needed} | {stock} | {p.get('bin_location', 'N/A')} | {available} |\n"
            )

    # Add procedures if present
    procedures = work_order.get("procedures", "")
    if procedures:
        card += f"\n**Procedures:**\n{procedures}\n"

    return card


def format_ticket_summary(ticket: dict) -> str:
    """Format a maintenance ticket as a summary card."""
    priority_icon = {
        "critical": "🔴",
        "high": "🟠",
        "medium": "🟡",
        "low": "🟢",
    }.get(ticket.get("priority", ""), "⚪")

    status_icon = {
        "open": "🟡",
        "assigned": "🔵",
        "in_progress": "🟠",
        "waiting_parts": "🔴",
        "completed": "🟢",
        "closed": "⚫",
    }.get(ticket.get("status", ""), "⚪")

    return f"""**{ticket.get('ticket_number', 'N/A')}** | {ticket.get('ticket_type', '')} | {priority_icon} {ticket.get('priority', '').upper()}
> **{ticket.get('title', 'No title')}**
> Machine: {ticket.get('machine_name', 'N/A')} ({ticket.get('machine_code', '')}) | Location: {ticket.get('location', 'N/A')}
> Status: {status_icon} {ticket.get('status', '').replace('_', ' ').title()} | Due: {ticket.get('due_date', 'N/A')}
"""


def format_tickets_table(tickets: list[dict]) -> str:
    """Format a list of tickets as a markdown table."""
    if not tickets:
        return "*No tickets found.*"

    priority_icon = {
        "critical": "🔴",
        "high": "🟠",
        "medium": "🟡",
        "low": "🟢",
    }

    table = "| # | Ticket | Type | Machine | Priority | Status | Due Date |\n"
    table += "|---|--------|------|---------|----------|--------|----------|\n"

    for i, t in enumerate(tickets, 1):
        p_icon = priority_icon.get(t.get("priority", ""), "⚪")
        table += (
            f"| {i} | {t.get('ticket_number', '')} | {t.get('ticket_type', '')} "
            f"| {t.get('machine_name', '')} | {p_icon} {t.get('priority', '').title()} "
            f"| {t.get('status', '').replace('_', ' ').title()} "
            f"| {t.get('due_date', 'N/A')} |\n"
        )

    return table


def format_inventory_table(parts: list[dict]) -> str:
    """Format inventory data as a markdown table with stock status indicators."""
    if not parts:
        return "*No inventory data found.*"

    table = "| Part # | Name | Category | On Hand | Reorder Level | Bin | Status |\n"
    table += "|--------|------|----------|---------|---------------|-----|--------|\n"

    for p in parts:
        stock = p.get("quantity_on_hand", 0)
        reorder = p.get("reorder_level", 0)
        if stock == 0:
            status = "🔴 Out of Stock"
        elif stock <= reorder:
            status = "🟡 Low Stock"
        else:
            status = "🟢 In Stock"

        table += (
            f"| {p.get('part_number', '')} | {p.get('part_name', '')} "
            f"| {p.get('category', '')} | {stock} | {reorder} "
            f"| {p.get('bin_location', 'N/A')} | {status} |\n"
        )

    return table


def format_procurement_status(requisition: dict) -> str:
    """Format a purchase requisition as a status card."""
    status_icon = {
        "requested": "📤",
        "quoted": "💬",
        "ordered": "📦",
        "delivered": "✅",
        "cancelled": "❌",
    }.get(requisition.get("status", ""), "⚪")

    return f"""### Purchase Requisition: {requisition.get('requisition_number', 'N/A')}

| Field | Details |
|-------|---------|
| **Part** | {requisition.get('part_name', 'N/A')} ({requisition.get('part_number', '')}) |
| **Quantity** | {requisition.get('quantity', 0)} |
| **Vendor** | {requisition.get('vendor_name', 'N/A')} |
| **Status** | {status_icon} {requisition.get('status', 'N/A').title()} |
| **Quoted Price** | ${requisition.get('quoted_price', 'TBD')} |
| **Expected Delivery** | {requisition.get('expected_delivery', 'TBD')} |
"""


def format_bom_table(bom_parts: list[dict]) -> str:
    """Format Bill of Materials as a markdown table."""
    if not bom_parts:
        return "*No BOM data found for this machine.*"

    table = "| Part # | Name | Category | Qty Required | In Stock | Critical |\n"
    table += "|--------|------|----------|-------------|----------|----------|\n"

    for p in bom_parts:
        critical = "Yes" if p.get("is_critical") else "No"
        stock = p.get("stock_on_hand", 0)
        stock_str = f"**{stock}**" if stock == 0 else str(stock)

        table += (
            f"| {p.get('part_number', '')} | {p.get('part_name', '')} "
            f"| {p.get('category', '')} | {p.get('quantity_required', 0)} "
            f"| {stock_str} | {critical} |\n"
        )

    return table


def format_maintenance_summary(
    tickets: list[dict],
    work_orders: list[dict] = None,
    inventory_alerts: list[dict] = None,
) -> str:
    """Format a comprehensive maintenance summary."""
    today = date.today().strftime("%B %d, %Y")

    summary = f"## Maintenance Summary - {today}\n\n"

    # Ticket overview
    cm_count = sum(1 for t in tickets if t.get("ticket_type") == "CM")
    pm_count = sum(1 for t in tickets if t.get("ticket_type") == "PM")
    summary += f"### Active Tickets: {len(tickets)}\n"
    summary += f"- **Corrective Maintenance (CM):** {cm_count}\n"
    summary += f"- **Preventive Maintenance (PM):** {pm_count}\n\n"

    # Priority breakdown
    critical = [t for t in tickets if t.get("priority") == "critical"]
    high = [t for t in tickets if t.get("priority") == "high"]
    if critical:
        summary += f"🔴 **{len(critical)} Critical** ticket(s) requiring immediate attention\n"
    if high:
        summary += f"🟠 **{len(high)} High priority** ticket(s)\n"
    summary += "\n"

    # Ticket details
    if tickets:
        summary += format_tickets_table(tickets) + "\n"

    # Work order status
    if work_orders:
        summary += f"### Active Work Orders: {len(work_orders)}\n\n"
        for wo in work_orders:
            summary += f"- **{wo.get('work_order_number', '')}**: {wo.get('description', '')} "
            summary += f"({wo.get('status', '').replace('_', ' ').title()})\n"
        summary += "\n"

    # Inventory alerts
    if inventory_alerts:
        summary += "### Inventory Alerts\n\n"
        summary += format_inventory_table(inventory_alerts) + "\n"

    return summary
