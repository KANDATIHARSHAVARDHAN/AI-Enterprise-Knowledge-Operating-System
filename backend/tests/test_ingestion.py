"""
EKOS Ingestion Unit Tests
Tests document parsing, chunking, and validation.
"""

import pytest
from app.ingestion.chunker import DocumentChunker
from app.ingestion.pipeline import IngestionPipeline


def test_chunker_recursive_split():
    """Test that text is chunked properly with recursive strategy."""
    chunker = DocumentChunker(chunk_size=100, chunk_overlap=10)

    text = "This is a simple sentence. This is another sentence that is slightly longer. And a third one."
    pages = [{"content": text, "metadata": {"source": "test.txt"}}]

    chunks = chunker.chunk_documents(pages, strategy="recursive")

    assert len(chunks) > 0
    for chunk in chunks:
        assert len(chunk["content"]) <= 100
        assert chunk["metadata"]["source"] == "test.txt"


def test_supported_extensions():
    """Test that the pipeline correctly lists supported extensions."""
    pipeline = IngestionPipeline()
    extensions = pipeline.get_supported_extensions()

    assert ".pdf" in extensions
    assert ".docx" in extensions
    assert ".csv" in extensions
    assert ".xlsx" in extensions
    assert ".txt" in extensions
    assert ".png" in extensions


def test_image_parser(tmp_path):
    """Test ImageParser parsing, exception handling, and resource safety."""
    from app.ingestion.parsers.image_parser import ImageParser
    from app.utils.exceptions import IngestionError
    from PIL import Image

    parser = ImageParser()

    # 1. Test missing file
    with pytest.raises(IngestionError) as exc_info:
        parser.parse(str(tmp_path / "nonexistent.png"))
    assert "File not found" in str(exc_info.value)

    # 2. Test unsupported extension
    bad_file = tmp_path / "test.txt"
    bad_file.write_text("dummy text")
    with pytest.raises(IngestionError) as exc_info:
        parser.parse(str(bad_file))
    assert "Unsupported image extension" in str(exc_info.value)

    # 3. Test valid image parsing
    img_path = tmp_path / "test.png"
    img = Image.new('RGB', (100, 100), color='blue')
    img.save(img_path)

    res = parser.parse(str(img_path))
    assert len(res) == 1
    assert res[0]["metadata"]["source"] == "test.png"
    assert res[0]["metadata"]["image_format"] == "PNG"
    assert res[0]["metadata"]["width"] == 100
    assert res[0]["metadata"]["height"] == 100
    assert "Format: PNG" in res[0]["content"]
    assert "Dimensions: 100x100" in res[0]["content"]
