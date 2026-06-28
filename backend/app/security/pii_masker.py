"""
EKOS PII Masker
Detects and masks personally identifiable information before sending to LLM.
"""

import re
from typing import Optional


class PIIMasker:
    """Detects and masks PII patterns in text."""

    PATTERNS = {
        "email": (
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            "[EMAIL_REDACTED]"
        ),
        "phone": (
            r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b',
            "[PHONE_REDACTED]"
        ),
        "ssn": (
            r'\b\d{3}-\d{2}-\d{4}\b',
            "[SSN_REDACTED]"
        ),
        "credit_card": (
            r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
            "[CARD_REDACTED]"
        ),
        "ip_address": (
            r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
            "[IP_REDACTED]"
        ),
    }

    def mask(self, text: str) -> tuple[str, list[dict]]:
        """
        Mask PII in text.

        Returns:
            Tuple of (masked_text, list of detected PII items)
        """
        detected = []
        masked_text = text

        for pii_type, (pattern, replacement) in self.PATTERNS.items():
            matches = re.findall(pattern, masked_text)
            if matches:
                for match in matches:
                    detected.append({
                        "type": pii_type,
                        "original": match,
                        "masked_as": replacement,
                    })
                masked_text = re.sub(pattern, replacement, masked_text)

        return masked_text, detected

    def contains_pii(self, text: str) -> bool:
        """Check if text contains any PII patterns."""
        for _, (pattern, _) in self.PATTERNS.items():
            if re.search(pattern, text):
                return True
        return False


# Singleton
_pii_masker: Optional[PIIMasker] = None


def get_pii_masker() -> PIIMasker:
    global _pii_masker
    if _pii_masker is None:
        _pii_masker = PIIMasker()
    return _pii_masker
