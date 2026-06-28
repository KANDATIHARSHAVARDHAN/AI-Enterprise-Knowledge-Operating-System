"""
EKOS Image Parser
Extracts text from images via OCR (Tesseract) and generates descriptions.
"""

from pathlib import Path
from typing import Optional
from PIL import Image
from app.utils.logger import logger
from app.utils.exceptions import IngestionError


class ImageParser:
    """Parse image files with OCR text extraction."""

    SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".gif", ".webp"}

    def __init__(self):
        self._tesseract_available = self._check_tesseract()

    def _check_tesseract(self) -> bool:
        """Check if Tesseract OCR is available."""
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            logger.warning("Tesseract OCR not available. Image text extraction will be limited.")
            return False

    def parse(self, file_path: str) -> list[dict]:
        """
        Parse an image file and extract OCR text.

        Returns:
            List with single dict containing extracted text and image info
        """
        path = Path(file_path)
        if not path.exists():
            raise IngestionError(f"File not found: {file_path}", filename=path.name)

        if path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            raise IngestionError(f"Unsupported image extension: {path.suffix}", filename=path.name)

        try:
            with Image.open(str(path)) as img:
                width, height = img.size
                img_format = img.format or path.suffix.upper().lstrip('.')

                # Extract text via OCR
                ocr_text = ""
                if self._tesseract_available:
                    ocr_text = self._extract_ocr_text(img)

                # Build content
                content_parts = [
                    f"Image: {path.name}",
                    f"Format: {img_format}",
                    f"Dimensions: {width}x{height}",
                ]

                if ocr_text:
                    content_parts.append(f"\nExtracted Text (OCR):\n{ocr_text}")
                else:
                    content_parts.append("\n[No text extracted from image]")

                content = "\n".join(content_parts)

                result = [{
                    "content": content,
                    "metadata": {
                        "source": path.name,
                        "file_type": "image",
                        "image_format": img_format,
                        "width": width,
                        "height": height,
                        "has_ocr_text": bool(ocr_text),
                        "file_path": str(path),
                    }
                }]

                logger.info(f"Parsed image: {path.name} ({width}x{height}, OCR: {bool(ocr_text)})")
                return result

        except Exception as e:
            raise IngestionError(f"Failed to parse image: {e}", filename=path.name)

    def _extract_ocr_text(self, img: Image.Image) -> str:
        """Extract text from image using Tesseract OCR."""
        try:
            import pytesseract
            text = pytesseract.image_to_string(img)
            return text.strip()
        except Exception as e:
            logger.warning(f"OCR extraction failed: {e}")
            return ""
