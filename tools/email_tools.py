"""
Email Tools
===========
LangChain @tool-decorated functions for email operations.
Used by Agent Roberto for vendor communication and Agent James for reports.
"""

import logging
from typing import Optional

from langchain_core.tools import tool

from services.email_service import get_email_service
from config.settings import EMAIL

logger = logging.getLogger(__name__)


@tool
async def send_email(to: str, subject: str, body: str) -> dict:
    """Send an email to a recipient.
    Args:
        to: Recipient email address.
        subject: Email subject line.
        body: Email body content (plain text).
    """
    service = get_email_service()
    result = await service.send_email(to=to, subject=subject, body=body)
    return result


@tool
async def send_vendor_quote_request(
    vendor_email: str,
    vendor_name: str,
    part_number: str,
    part_name: str,
    quantity: int,
    requisition_number: str,
    urgency: str = "standard",
) -> dict:
    """Send a quote request email to a vendor for a specific part.
    Args:
        vendor_email: Vendor's email address.
        vendor_name: Vendor's company name.
        part_number: The part number to request.
        part_name: The part name.
        quantity: Quantity needed.
        requisition_number: Purchase requisition reference number.
        urgency: Urgency level - standard, urgent, or critical.
    """
    from config.prompts import ROBERTO_VENDOR_EMAIL_TEMPLATE

    subject = f"Quote Request - {requisition_number} | {part_name} ({part_number})"
    body = ROBERTO_VENDOR_EMAIL_TEMPLATE.format(
        requisition_number=requisition_number,
        part_number=part_number,
        part_name=part_name,
        quantity=quantity,
        urgency=urgency,
        vendor_name=vendor_name,
    )

    service = get_email_service()
    result = await service.send_email(to=vendor_email, subject=subject, body=body)
    logger.info(f"Vendor quote request sent to {vendor_name} ({vendor_email}): {requisition_number}")
    return result


@tool
async def read_vendor_responses(
    requisition_number: str, since_minutes: int = 30
) -> list[dict]:
    """Read email inbox for vendor responses matching a requisition number.
    Args:
        requisition_number: The requisition number to search for in email subjects.
        since_minutes: Only check emails from the last N minutes.
    """
    service = get_email_service()
    emails = await service.read_emails(
        subject_filter=requisition_number,
        since_minutes=since_minutes,
        unread_only=True,
    )
    return emails


@tool
async def poll_vendor_response(
    requisition_number: str,
    timeout_minutes: int = 10,
) -> Optional[dict]:
    """Poll inbox for a vendor response, waiting up to timeout_minutes.
    Args:
        requisition_number: The requisition number to watch for.
        timeout_minutes: Maximum minutes to wait for a response.
    """
    service = get_email_service()
    response = await service.poll_for_response(
        subject_filter=requisition_number,
        timeout_minutes=timeout_minutes,
    )
    return response


@tool
async def send_maintenance_report(
    recipient_email: str, subject: str, report_body: str
) -> dict:
    """Send a maintenance status report email.
    Args:
        recipient_email: Email address to send the report to.
        subject: Email subject for the report.
        report_body: Full report content.
    """
    service = get_email_service()
    result = await service.send_email(
        to=recipient_email, subject=subject, body=report_body
    )
    return result
