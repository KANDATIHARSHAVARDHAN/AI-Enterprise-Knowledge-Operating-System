"""
EKOS Metadata Extractor
Extracts structured metadata from documents for filtering and search.
"""

from pathlib import Path
from datetime import datetime
from typing import Optional


class MetadataExtractor:
    """Extract metadata from document files."""

    def extract(self, file_path: str, file_type: str) -> dict:
        """
        Extract metadata from a file.

        Returns:
            Dict with extracted metadata fields
        """
        path = Path(file_path)

        metadata = {
            "filename": path.name,
            "file_type": file_type,
            "file_extension": path.suffix.lower(),
            "file_size_bytes": path.stat().st_size if path.exists() else 0,
            "created_at": datetime.utcnow().isoformat(),
            "ingested_at": datetime.utcnow().isoformat(),
        }

        # Try to get file creation and modification times
        if path.exists():
            stat = path.stat()
            metadata["file_modified_at"] = datetime.fromtimestamp(stat.st_mtime).isoformat()

        return metadata
