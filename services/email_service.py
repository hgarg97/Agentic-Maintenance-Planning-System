"""
Email Service
=============
Gmail SMTP (send) + IMAP (poll/read) for vendor communication and reports.
Uses App Password authentication for POC simplicity.
"""

import asyncio
import email
import imaplib
import logging
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Callable, Optional

from config.settings import EMAIL

logger = logging.getLogger(__name__)


class EmailService:
    """Gmail SMTP + IMAP email service."""

    def __init__(self):
        self.smtp_server = EMAIL["smtp_server"]
        self.smtp_port = EMAIL["smtp_port"]
        self.imap_server = EMAIL["imap_server"]
        self.imap_port = EMAIL["imap_port"]
        self.sender_email = EMAIL["sender_email"]
        self.sender_password = EMAIL["sender_password"]
        self.sender_name = EMAIL["sender_name"]
        self._polling = False

    async def send_email(
        self, to: str, subject: str, body: str, html: bool = False
    ) -> dict:
        """
        Send an email via Gmail SMTP.

        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body (plain text or HTML)
            html: If True, send as HTML email

        Returns:
            dict with status and message_id
        """
        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = f"{self.sender_name} <{self.sender_email}>"
            msg["To"] = to
            msg["Subject"] = subject

            content_type = "html" if html else "plain"
            msg.attach(MIMEText(body, content_type))

            # Run SMTP in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._send_smtp, msg)

            logger.info(f"Email sent to {to}: {subject}")
            return {"status": "sent", "to": to, "subject": subject}

        except Exception as e:
            logger.error(f"Failed to send email to {to}: {e}")
            return {"status": "failed", "error": str(e)}

    def _send_smtp(self, msg: MIMEMultipart) -> None:
        """Synchronous SMTP send (runs in executor)."""
        with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(self.sender_email, self.sender_password)
            server.send_message(msg)

    async def read_emails(
        self,
        subject_filter: Optional[str] = None,
        since_minutes: int = 30,
        unread_only: bool = True,
    ) -> list[dict]:
        """
        Read emails from Gmail IMAP inbox.

        Args:
            subject_filter: Filter by subject (substring match)
            since_minutes: Only read emails from the last N minutes
            unread_only: If True, only read unread emails

        Returns:
            List of email dicts with from, subject, body, date
        """
        try:
            loop = asyncio.get_event_loop()
            emails = await loop.run_in_executor(
                None, self._read_imap, subject_filter, since_minutes, unread_only
            )
            return emails
        except Exception as e:
            logger.error(f"Failed to read emails: {e}")
            return []

    def _read_imap(
        self,
        subject_filter: Optional[str],
        since_minutes: int,
        unread_only: bool,
    ) -> list[dict]:
        """Synchronous IMAP read (runs in executor)."""
        emails_found = []

        mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
        mail.login(self.sender_email, self.sender_password)
        mail.select("inbox")

        # Build search criteria
        criteria = []
        if unread_only:
            criteria.append("UNSEEN")

        since_date = (datetime.now() - timedelta(minutes=since_minutes)).strftime(
            "%d-%b-%Y"
        )
        criteria.append(f'SINCE "{since_date}"')

        if subject_filter:
            criteria.append(f'SUBJECT "{subject_filter}"')

        search_query = " ".join(criteria) if criteria else "ALL"
        _, message_numbers = mail.search(None, search_query)

        for num in message_numbers[0].split():
            _, msg_data = mail.fetch(num, "(RFC822)")
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            # Extract body
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode(
                            "utf-8", errors="replace"
                        )
                        break
            else:
                body = msg.get_payload(decode=True).decode("utf-8", errors="replace")

            emails_found.append(
                {
                    "from": msg["From"],
                    "subject": msg["Subject"],
                    "body": body.strip(),
                    "date": msg["Date"],
                    "message_id": msg["Message-ID"],
                }
            )

        mail.logout()
        return emails_found

    async def poll_for_response(
        self,
        subject_filter: str,
        timeout_minutes: Optional[int] = None,
        poll_interval: Optional[int] = None,
    ) -> Optional[dict]:
        """
        Poll inbox for a specific email response.

        Args:
            subject_filter: Subject to filter for (e.g., requisition number)
            timeout_minutes: Max wait time (defaults to EMAIL config)
            poll_interval: Seconds between polls (defaults to EMAIL config)

        Returns:
            First matching email dict, or None if timeout
        """
        timeout = timeout_minutes or EMAIL["poll_timeout_minutes"]
        interval = poll_interval or EMAIL["poll_interval_seconds"]
        deadline = asyncio.get_event_loop().time() + (timeout * 60)

        logger.info(
            f"Polling for email with subject containing: {subject_filter} "
            f"(timeout: {timeout}min, interval: {interval}s)"
        )

        while asyncio.get_event_loop().time() < deadline:
            emails = await self.read_emails(
                subject_filter=subject_filter,
                since_minutes=timeout,
                unread_only=True,
            )

            if emails:
                logger.info(f"Found vendor response: {emails[0]['subject']}")
                return emails[0]

            await asyncio.sleep(interval)

        logger.warning(f"Polling timeout for subject: {subject_filter}")
        return None


# Module-level singleton
_email_service: Optional[EmailService] = None


def get_email_service() -> EmailService:
    """Get or create the email service singleton."""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
