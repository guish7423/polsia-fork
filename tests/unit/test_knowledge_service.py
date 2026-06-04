"""Test KnowledgeService — document CRUD, chunking, upload logic."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.knowledge_service import (
    KnowledgeService,
    chunk_text,
)


class TestChunkText:
    """Unit tests for the chunk_text utility."""

    def test_chunk_text_basic(self):
        """Basic chunking with default size/overlap."""
        words = ["word"] * 600
        text = " ".join(words)
        chunks = chunk_text(text, chunk_size=200, overlap=20)
        # step = 200-20 = 180, range(0,600,180) = 0,180,360,540 → 4 chunks
        assert len(chunks) == 4
        # each chunk has at most 200 words
        for chunk in chunks:
            assert len(chunk.split()) <= 200

    def test_chunk_text_small(self):
        """Text smaller than chunk_size returns one chunk."""
        text = "hello world this is a test"
        chunks = chunk_text(text, chunk_size=500, overlap=50)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_chunk_text_overlap(self):
        """Consecutive chunks share overlapping words."""
        text = "one two three four five six seven eight nine ten"
        chunks = chunk_text(text, chunk_size=4, overlap=1)
        assert len(chunks) >= 2
        # last word of chunk 0 should be the first word of overlap
        if len(chunks) >= 2:
            chunk0_words = chunks[0].split()
            chunk1_words = chunks[1].split()
            # overlap means there's 1 shared word at the boundary
            assert len(chunk0_words) == 4
            assert chunk0_words[-1] == chunk1_words[0]

    def test_chunk_text_empty(self):
        """Empty text returns empty list."""
        assert chunk_text("") == []

    def test_chunk_text_exact(self):
        """Text with exactly chunk_size words returns one chunk when no overlap."""
        words = ["w"] * 500
        text = " ".join(words)
        chunks = chunk_text(text, chunk_size=500, overlap=0)
        assert len(chunks) == 1


@pytest.mark.asyncio
class TestKnowledgeService:
    """Integration tests for KnowledgeService CRUD methods."""

    async def test_create_document(self, async_db_session: AsyncSession):
        """Create a document record via service."""
        doc = await KnowledgeService.create_document(
            async_db_session,
            tenant_id=1,
            filename="report.pdf",
            content_type="application/pdf",
            file_size=2048,
        )
        assert doc.id is not None
        assert doc.tenant_id == 1
        assert doc.filename == "report.pdf"
        assert doc.status == "uploading"

    async def test_list_documents(self, async_db_session: AsyncSession):
        """List all documents for a tenant."""
        for i in range(3):
            await KnowledgeService.create_document(
                async_db_session,
                tenant_id=1,
                filename=f"doc_{i}.txt",
                content_type="text/plain",
                file_size=100,
            )
        docs = await KnowledgeService.list_documents(async_db_session, tenant_id=1)
        assert len(docs) == 3

    async def test_list_documents_with_status_filter(
        self, async_db_session: AsyncSession
    ):
        """Filter documents by status."""
        await KnowledgeService.create_document(
            async_db_session, tenant_id=1, filename="r1.txt",
            content_type="text/plain", file_size=100,
        )
        doc = await KnowledgeService.create_document(
            async_db_session, tenant_id=1, filename="r2.txt",
            content_type="text/plain", file_size=100,
        )
        doc.status = "ready"
        await async_db_session.flush()

        ready_docs = await KnowledgeService.list_documents(
            async_db_session, tenant_id=1, status="ready"
        )
        assert len(ready_docs) == 1
        assert ready_docs[0].filename == "r2.txt"

    async def test_get_document(self, async_db_session: AsyncSession):
        """Get a single document by ID."""
        doc = await KnowledgeService.create_document(
            async_db_session, tenant_id=1, filename="target.pdf",
            content_type="application/pdf", file_size=4096,
        )
        found = await KnowledgeService.get_document(
            async_db_session, doc_id=doc.id, tenant_id=1
        )
        assert found is not None
        assert found.id == doc.id

    async def test_get_document_wrong_tenant(
        self, async_db_session: AsyncSession
    ):
        """Document from another tenant should not be visible."""
        doc = await KnowledgeService.create_document(
            async_db_session, tenant_id=1, filename="secret.txt",
            content_type="text/plain", file_size=100,
        )
        found = await KnowledgeService.get_document(
            async_db_session, doc_id=doc.id, tenant_id=2
        )
        assert found is None

    async def test_soft_delete_document(self, async_db_session: AsyncSession):
        """Soft delete marks document as deleted."""
        doc = await KnowledgeService.create_document(
            async_db_session, tenant_id=1, filename="delete_me.txt",
            content_type="text/plain", file_size=100,
        )
        result = await KnowledgeService.soft_delete_document(
            async_db_session, doc_id=doc.id, tenant_id=1
        )
        assert result is True

        # Deleted document should not appear in list
        docs = await KnowledgeService.list_documents(
            async_db_session, tenant_id=1
        )
        assert len(docs) == 0

    async def test_search_documents(self, async_db_session: AsyncSession):
        """SQL LIKE search across document filenames."""
        await KnowledgeService.create_document(
            async_db_session, tenant_id=1, filename="quarterly_report_2026.pdf",
            content_type="application/pdf", file_size=1000,
        )
        await KnowledgeService.create_document(
            async_db_session, tenant_id=1, filename="meeting_notes.txt",
            content_type="text/plain", file_size=500,
        )
        results = await KnowledgeService.search_documents(
            async_db_session, tenant_id=1, query="report"
        )
        assert len(results) == 1
        assert results[0].filename == "quarterly_report_2026.pdf"

    async def test_search_documents_returns_empty(
        self, async_db_session: AsyncSession
    ):
        """No match returns empty list."""
        await KnowledgeService.create_document(
            async_db_session, tenant_id=1, filename="some_file.txt",
            content_type="text/plain", file_size=200,
        )
        results = await KnowledgeService.search_documents(
            async_db_session, tenant_id=1, query="nonexistent"
        )
        assert results == []
