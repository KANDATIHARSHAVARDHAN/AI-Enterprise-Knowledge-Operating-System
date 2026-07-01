"""
EKOS Document Ingestion Pipeline
Orchestrates the full pipeline: parse → chunk → embed → store in FAISS + MySQL.
"""

from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.utils.logger import logger
from app.utils.exceptions import IngestionError, UnsupportedFileTypeError
from app.ingestion.parsers.pdf_parser import PDFParser
from app.ingestion.parsers.word_parser import WordParser
from app.ingestion.parsers.excel_parser import ExcelParser
from app.ingestion.parsers.csv_parser import CSVParser
from app.ingestion.parsers.image_parser import ImageParser
from app.ingestion.parsers.email_parser import EmailParser
from app.ingestion.parsers.text_parser import TextParser
from app.ingestion.chunker import DocumentChunker
from app.ingestion.embedder import get_embedder
from app.ingestion.metadata_extractor import MetadataExtractor
from app.db.models import Document, DocumentChunk


class IngestionPipeline:
    """Orchestrates the complete document ingestion workflow."""

    # Map file extensions to parsers
    PARSER_MAP = {
        ".pdf": PDFParser,
        ".docx": WordParser,
        ".doc": WordParser,
        ".xlsx": ExcelParser,
        ".xls": ExcelParser,
        ".csv": CSVParser,
        ".tsv": CSVParser,
        ".png": ImageParser,
        ".jpg": ImageParser,
        ".jpeg": ImageParser,
        ".bmp": ImageParser,
        ".tiff": ImageParser,
        ".gif": ImageParser,
        ".webp": ImageParser,
        ".eml": EmailParser,
        ".txt": TextParser,
        ".md": TextParser,
        ".text": TextParser,
        ".log": TextParser,
        ".rst": TextParser,
    }

    def __init__(self):
        self.settings = get_settings()
        self.chunker = DocumentChunker()
        self.embedder = get_embedder()
        self.metadata_extractor = MetadataExtractor()

    def get_parser(self, file_extension: str):
        """Get the appropriate parser for a file extension."""
        parser_class = self.PARSER_MAP.get(file_extension.lower())
        if not parser_class:
            raise UnsupportedFileTypeError(file_extension)
        return parser_class()

    async def ingest_document(
        self,
        file_path: str,
        document_id: int,
        db: AsyncSession,
        vector_store=None,
    ) -> dict:
        """
        Run the full ingestion pipeline for a single document.

        Args:
            file_path: Path to the uploaded file
            document_id: ID of the document record in MySQL
            db: Async database session
            vector_store: FAISS vector store instance

        Returns:
            Dict with ingestion results (chunk_count, status)
        """
        path = Path(file_path)
        extension = path.suffix.lower()

        logger.info(f"Starting ingestion for document {document_id}: {path.name}")

        # Update document status to processing
        doc = await db.get(Document, document_id)
        if doc:
            doc.status = "processing"
            await db.commit()

        try:
            # Step 1: Parse the document
            parser = self.get_parser(extension)
            pages = parser.parse(str(path))

            if not pages:
                raise IngestionError("No content extracted from document", filename=path.name)

            logger.info(f"Parsed {len(pages)} pages from {path.name}")

            # Step 2: Chunk the document
            chunks = self.chunker.chunk_documents(pages, strategy="recursive")
            logger.info(f"Created {len(chunks)} chunks from {path.name}")

            # Step 3: Generate embeddings
            chunk_texts = [c["content"] for c in chunks]
            embeddings = self.embedder.embed_batch(chunk_texts)
            logger.info(f"Generated {len(embeddings)} embeddings")

            # Step 4: Store chunks in MySQL
            chunk_records = []
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                chunk_record = DocumentChunk(
                    document_id=document_id,
                    chunk_index=i,
                    content=chunk["content"],
                    content_hash=chunk["content_hash"],
                    metadata_json=chunk["metadata"],
                    embedding_id=f"doc{document_id}_chunk{i}",
                    token_count=chunk.get("token_count", 0),
                )
                db.add(chunk_record)
                chunk_records.append(chunk_record)

            await db.flush()

            # Step 5: Add embeddings to FAISS vector store
            if vector_store:
                embedding_ids = [f"doc{document_id}_chunk{i}" for i in range(len(embeddings))]
                chunk_metadata = [
                    {
                        "chunk_id": chunk_records[i].id if chunk_records[i].id else i,
                        "document_id": document_id,
                        "embedding_id": embedding_ids[i],
                        "source": chunks[i]["metadata"].get("source", ""),
                        "content": chunks[i]["content"],
                        "content_preview": chunks[i]["content"][:200],
                    }
                    for i in range(len(chunks))
                ]
                vector_store.add_embeddings(embeddings, chunk_metadata, embedding_ids)
                vector_store.save()
                logger.info(f"Added {len(embeddings)} vectors to FAISS index")

            # Step 6: Update document status
            if doc:
                doc.status = "completed"
                doc.chunk_count = len(chunks)
                doc.metadata_json = self.metadata_extractor.extract(str(path), extension)

            await db.commit()

            result = {
                "status": "completed",
                "chunk_count": len(chunks),
                "embedding_count": len(embeddings),
                "document_id": document_id,
            }

            logger.info(f"Ingestion completed for {path.name}: {len(chunks)} chunks")
            return result

        except Exception as e:
            # Update document status to failed
            try:
                doc = await db.get(Document, document_id)
                if doc:
                    doc.status = "failed"
                    doc.error_message = str(e)[:1000]
                    await db.commit()
            except Exception as commit_err:
                logger.error(f"Failed to update document status: {commit_err}")

            logger.error(f"Ingestion failed for {path.name}: {e}")
            # Raise RuntimeError (not IngestionError) so the caller knows
            # the DB error status has already been committed.
            raise RuntimeError(f"Ingestion failed for {path.name}: {e}") from e

    @staticmethod
    def get_supported_extensions() -> list[str]:
        """Return list of supported file extensions."""
        return list(IngestionPipeline.PARSER_MAP.keys())
