"""Knowledge service — document upload, CRUD, chunking, and search.

Phase 1: SQL-based storage only.
Phase 2 (Task 2): Adds ChromaDB embedding + vector search.
"""

import os
import tempfile
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.knowledge_document import KnowledgeDocument


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into overlapping word-based chunks.

    Phase 1 simplification: word-based (text.split()) — not optimal for
    Chinese text but functional for v1. Phase 2 may switch to a smarter
    tokenizer.
    """
    if not text:
        return []
    words = text.split()
    chunks: list[str] = []
    step = chunk_size - overlap
    if step <= 0:
        # fallback: no overlap if step would be non-positive
        step = chunk_size
    for i in range(0, len(words), step):
        chunk = " ".join(words[i : i + chunk_size])
        if chunk:
            chunks.append(chunk)
    return chunks


class KnowledgeService:
    """CRUD + upload for KnowledgeDocument records."""

    @staticmethod
    async def create_document(
        db: AsyncSession,
        tenant_id: int,
        filename: str,
        content_type: str,
        file_size: int,
    ) -> KnowledgeDocument:
        """Create a new KnowledgeDocument record."""
        doc = KnowledgeDocument(
            tenant_id=tenant_id,
            filename=filename,
            content_type=content_type,
            file_size=file_size,
        )
        db.add(doc)
        await db.flush()
        await db.refresh(doc)
        return doc

    @staticmethod
    async def list_documents(
        db: AsyncSession,
        tenant_id: int,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[KnowledgeDocument]:
        """List documents for a tenant, optionally filtered by status."""
        query = (
            select(KnowledgeDocument)
            .where(KnowledgeDocument.tenant_id == tenant_id)
            .where(KnowledgeDocument.status != "deleted")
            .order_by(KnowledgeDocument.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        if status:
            query = query.where(KnowledgeDocument.status == status)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_document(
        db: AsyncSession,
        doc_id: int,
        tenant_id: int,
    ) -> KnowledgeDocument | None:
        """Get a single document by ID (tenant-scoped)."""
        result = await db.execute(
            select(KnowledgeDocument).where(
                KnowledgeDocument.id == doc_id,
                KnowledgeDocument.tenant_id == tenant_id,
                KnowledgeDocument.status != "deleted",
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def soft_delete_document(
        db: AsyncSession,
        doc_id: int,
        tenant_id: int,
    ) -> bool:
        """Soft-delete a document by setting status='deleted'.

        Returns True if a row was affected, False if not found/wrong tenant.
        """
        doc = await KnowledgeService.get_document(db, doc_id, tenant_id)
        if doc is None:
            return False
        doc.status = "deleted"
        await db.flush()
        return True

    @staticmethod
    async def search_documents(
        db: AsyncSession,
        tenant_id: int,
        query: str,
        limit: int = 20,
    ) -> list[KnowledgeDocument]:
        """SQL LIKE search on filename (fallback for when vector search is unavailable)."""
        stmt = (
            select(KnowledgeDocument)
            .where(KnowledgeDocument.tenant_id == tenant_id)
            .where(KnowledgeDocument.status != "deleted")
            .where(KnowledgeDocument.filename.ilike(f"%{query}%"))
            .order_by(KnowledgeDocument.created_at.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def process_upload(
        db: AsyncSession,
        tenant_id: int,
        filename: str,
        content_type: str,
        content: bytes,
    ) -> KnowledgeDocument:
        """Process an uploaded file: create document record, parse content, chunk.

        Handles:
        - TXT/MD: direct text parsing
        - PDF: PyMuPDF extraction (if pymupdf is installed)
        - Other: stored as-is with error status

        Returns the KnowledgeDocument with status='ready' and chunk_count set.
        """
        doc = await KnowledgeService.create_document(
            db,
            tenant_id=tenant_id,
            filename=filename,
            content_type=content_type,
            file_size=len(content),
        )

        try:
            text = _parse_file_content(content, content_type, filename)
            if not text or not text.strip():
                doc.status = "error"
                doc.error_message = "No extractable text content found"
                await db.flush()
                return doc

            chunks = chunk_text(text)
            doc.chunk_count = len(chunks)
            doc.status = "ready"
            await db.flush()
            await db.refresh(doc)

            # Phase 2: Asynchronously embed and store in ChromaDB (fail-open)
            if settings.rag_enabled and chunks:
                try:
                    await KnowledgeService._ingest_chunks(
                        db, doc.id, tenant_id, chunks, filename,
                    )
                except Exception:
                    pass

            return doc
        except Exception as exc:
            doc.status = "error"
            doc.error_message = str(exc)
            await db.flush()
            await db.refresh(doc)
            return doc


    @staticmethod
    async def _ingest_chunks(
        db: AsyncSession,
        doc_id: int,
        tenant_id: int,
        chunks: list[str],
        filename: str,
    ) -> int:
        """Embed document chunks and store in ChromaDB knowledge_base collection.

        Returns the number of successfully embedded chunks.
        This is called automatically during ``process_upload``.
        """
        try:
            from app.core.chroma_client import get_knowledge_collection
            from app.services.embedding_service import get_embedding_service

            svc = get_embedding_service()
            collection = get_knowledge_collection()

            chunk_dicts = [
                {
                    "id": f"doc{doc_id}_chunk{i}",
                    "text": chunk,
                    "metadata": {
                        "doc_id": str(doc_id),
                        "filename": filename,
                        "chunk_index": i,
                        "tenant_id": str(tenant_id),
                    },
                }
                for i, chunk in enumerate(chunks)
            ]

            embedded = await svc.batch_ingest_chunks(chunk_dicts, collection)
            return embedded
        except Exception:
            return 0


def _parse_file_content(content: bytes, content_type: str, filename: str) -> str:
    """Extract text from uploaded file content.

    Supports TXT, MD (direct text), PDF (via PyMuPDF), and other text-based formats.
    """
    # Plain text formats
    if content_type in ("text/plain", "text/markdown", "text/csv", "text/html"):
        return content.decode("utf-8", errors="replace")

    # Fallback: check extension for .md, .txt, .csv
    ext = Path(filename).suffix.lower()
    if ext in (".txt", ".md", ".csv", ".html", ".htm", ".json", ".xml", ".yaml", ".yml"):
        return content.decode("utf-8", errors="replace")

    # PDF via PyMuPDF
    if content_type == "application/pdf" or ext == ".pdf":
        return _extract_pdf_text(content)

    raise ValueError(f"Unsupported content type: {content_type}")


def _extract_pdf_text(content: bytes) -> str:
    """Extract text from a PDF file using PyMuPDF (fitz)."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise ImportError(
            "PyMuPDF is required to parse PDF files. "
            "Install it with: pip install pymupdf"
        )

    text_parts: list[str] = []
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        doc = fitz.open(tmp_path)
        for page in doc:
            text_parts.append(page.get_text())
        doc.close()
    finally:
        os.unlink(tmp_path)

    return "\n".join(text_parts)
