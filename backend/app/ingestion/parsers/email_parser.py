"""
EKOS Email Parser
Extracts text, subject, sender info from .eml email files.
"""

import email
from email import policy
from pathlib import Path
from app.utils.logger import logger
from app.utils.exceptions import IngestionError


class EmailParser:
    """Parse .eml email files and extract content."""

    SUPPORTED_EXTENSIONS = {".eml"}

    def parse(self, file_path: str) -> list[dict]:
        """Parse an .eml file and extract email content."""
        path = Path(file_path)
        if not path.exists():
            raise IngestionError(f"File not found: {file_path}", filename=path.name)

        try:
            with open(str(path), "rb") as f:
                msg = email.message_from_binary_file(f, policy=policy.default)

            subject = msg.get("Subject", "No Subject")
            sender = msg.get("From", "Unknown Sender")
            recipients = msg.get("To", "Unknown")
            date = msg.get("Date", "Unknown Date")
            cc = msg.get("Cc", "")

            # Extract body
            body = self._extract_body(msg)

            # Extract attachments info
            attachments = self._list_attachments(msg)

            content_parts = [
                f"Email Subject: {subject}",
                f"From: {sender}",
                f"To: {recipients}",
            ]
            if cc:
                content_parts.append(f"Cc: {cc}")
            content_parts.extend([
                f"Date: {date}",
                f"\n--- Email Body ---\n{body}",
            ])

            if attachments:
                content_parts.append(f"\nAttachments: {', '.join(attachments)}")

            content = "\n".join(content_parts)

            result = [{
                "content": content,
                "metadata": {
                    "source": path.name,
                    "file_type": "email",
                    "subject": subject,
                    "sender": sender,
                    "recipients": recipients,
                    "date": date,
                    "attachment_count": len(attachments),
                    "file_path": str(path),
                }
            }]

            logger.info(f"Parsed email: {path.name} (Subject: {subject})")
            return result

        except Exception as e:
            raise IngestionError(f"Failed to parse email: {e}", filename=path.name)

    def _extract_body(self, msg) -> str:
        """Extract the email body text."""
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        body += payload.decode("utf-8", errors="replace")
                elif content_type == "text/html" and not body:
                    payload = part.get_payload(decode=True)
                    if payload:
                        # Basic HTML stripping
                        import re
                        html_text = payload.decode("utf-8", errors="replace")
                        body = re.sub(r"<[^>]+>", " ", html_text)
                        body = re.sub(r"\s+", " ", body).strip()
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                body = payload.decode("utf-8", errors="replace")
        return body.strip() or "[Empty email body]"

    def _list_attachments(self, msg) -> list[str]:
        """List attachment filenames."""
        attachments = []
        if msg.is_multipart():
            for part in msg.walk():
                filename = part.get_filename()
                if filename:
                    attachments.append(filename)
        return attachments
