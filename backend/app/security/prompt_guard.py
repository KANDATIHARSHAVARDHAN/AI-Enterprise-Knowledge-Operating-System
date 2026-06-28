"""
EKOS Prompt Guard
Detects and blocks prompt injection attempts.
"""

import re
from app.utils.exceptions import PromptInjectionError
from app.utils.logger import logger


class PromptGuard:
    """Detects prompt injection patterns in user input."""

    INJECTION_PATTERNS = [
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"ignore\s+(all\s+)?above",
        r"disregard\s+(all\s+)?previous",
        r"forget\s+(all\s+)?previous",
        r"you\s+are\s+now\s+",
        r"act\s+as\s+(a|an)\s+",
        r"pretend\s+(to\s+be|you\s+are)",
        r"system\s*:\s*",
        r"<\|?system\|?>",
        r"\[\[system\]\]",
        r"ADMIN\s*OVERRIDE",
        r"jailbreak",
        r"DAN\s+mode",
        r"developer\s+mode",
    ]

    def __init__(self, strict: bool = False):
        self.strict = strict
        self.compiled_patterns = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.INJECTION_PATTERNS
        ]

    def check(self, text: str) -> tuple[bool, str]:
        """
        Check text for prompt injection patterns.

        Returns:
            Tuple of (is_safe, reason)
        """
        for pattern in self.compiled_patterns:
            match = pattern.search(text)
            if match:
                reason = f"Matched injection pattern: '{match.group()}'"
                logger.warning(f"Prompt injection detected: {reason}")
                return False, reason

        return True, "clean"

    def sanitize(self, text: str) -> str:
        """Remove potential injection patterns from text."""
        sanitized = text
        for pattern in self.compiled_patterns:
            sanitized = pattern.sub("[FILTERED]", sanitized)
        return sanitized

    def guard(self, text: str) -> str:
        """
        Check and raise if injection detected.

        Returns:
            The original text if safe

        Raises:
            PromptInjectionError if injection detected
        """
        is_safe, reason = self.check(text)
        if not is_safe:
            raise PromptInjectionError(reason)
        return text


# Singleton
_prompt_guard = None


def get_prompt_guard() -> PromptGuard:
    global _prompt_guard
    if _prompt_guard is None:
        _prompt_guard = PromptGuard()
    return _prompt_guard
