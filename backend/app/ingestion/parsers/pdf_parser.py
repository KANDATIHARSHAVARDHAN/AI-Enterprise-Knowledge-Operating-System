"""
EKOS PDF Parser
Extracts text from PDF files using PyMuPDF with table detection support.
"""

from pathlib import Path
import fitz  # PyMuPDF
from app.utils.logger import logger
from app.utils.exceptions import IngestionError


class PDFParser:
    """Parse PDF files and extract text content."""

    SUPPORTED_EXTENSIONS = {".pdf"}

    def parse(self, file_path: str) -> list[dict]:
        """
        Parse a PDF file and extract text by page.

        Args:
            file_path: Path to the PDF file

        Returns:
            List of dicts with 'content', 'metadata' per page
        """
        path = Path(file_path)
        if not path.exists():
            raise IngestionError(f"File not found: {file_path}", filename=path.name)

        if path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            raise IngestionError(f"Not a PDF file: {file_path}", filename=path.name)

        pages = []
        try:
            doc = fitz.open(str(path))
            for page_num, page in enumerate(doc, 1):
                text = page.get_text("text")
                if text.strip():
                    # Try to extract tables as well
                    tables_text = self._extract_tables(page)

                    content = text.strip()
                    if tables_text:
                        content += "\n\n[Tables]\n" + tables_text

                    pages.append({
                        "content": content,
                        "metadata": {
                            "source": path.name,
                            "file_type": "pdf",
                            "page_number": page_num,
                            "total_pages": len(doc),
                            "file_path": str(path),
                        }
                    })

            doc.close()
            logger.info(f"Parsed PDF: {path.name} ({len(pages)} pages with content)")

        except fitz.FitzError as e:
            raise IngestionError(f"Failed to parse PDF: {e}", filename=path.name)

        return pages

    def _extract_tables(self, page) -> str:
        """Attempt to extract tables from a page."""
        try:
            tables = page.find_tables()
            if not tables or len(tables.tables) == 0:
                return ""

            table_texts = []
            for table in tables:
                rows = table.extract()
                if rows:
                    # Convert to text format
                    header = rows[0] if rows else []
                    table_text = " | ".join(str(cell or "") for cell in header) + "\n"
                    table_text += "-" * 40 + "\n"
                    for row in rows[1:]:
                        table_text += " | ".join(str(cell or "") for cell in row) + "\n"
                    table_texts.append(table_text)

            return "\n".join(table_texts)
        except Exception:
            return ""
