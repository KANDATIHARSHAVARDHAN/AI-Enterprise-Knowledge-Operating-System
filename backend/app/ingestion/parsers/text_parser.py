"""
EKOS Text Parser
Extracts content from plain text and markdown files.
"""

from pathlib import Path
from app.utils.logger import logger
from app.utils.exceptions import IngestionError


class TextParser:
    """Parse plain text and markdown files."""

    SUPPORTED_EXTENSIONS = {".txt", ".md", ".text", ".log", ".rst"}

    def parse(self, file_path: str) -> list[dict]:
        """Parse a text file and return its content."""
        path = Path(file_path)
        if not path.exists():
            raise IngestionError(f"File not found: {file_path}", filename=path.name)

        try:
            with open(str(path), "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            if not content.strip():
                return []

            result = [{
                "content": content.strip(),
                "metadata": {
                    "source": path.name,
                    "file_type": "text",
                    "char_count": len(content),
                    "line_count": content.count("\n") + 1,
                    "file_path": str(path),
                }
            }]

            logger.info(f"Parsed text: {path.name} ({len(content)} chars)")
            return result

        except Exception as e:
            raise IngestionError(f"Failed to parse text file: {e}", filename=path.name)
