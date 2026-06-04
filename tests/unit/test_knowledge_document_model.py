"""Test KnowledgeDocument ORM model — fields, constraints, relationships."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_document import KnowledgeDocument


@pytest.mark.asyncio
async def test_create_knowledge_document(async_db_session: AsyncSession):
    """Create a KnowledgeDocument with all required fields."""
    doc = KnowledgeDocument(
        tenant_id=1,
        filename="test_doc.txt",
        content_type="text/plain",
        file_size=1024,
        status="ready",
        chunk_count=5,
    )
    async_db_session.add(doc)
    await async_db_session.flush()
    await async_db_session.refresh(doc)

    assert doc.id is not None
    assert doc.tenant_id == 1
    assert doc.filename == "test_doc.txt"
    assert doc.content_type == "text/plain"
    assert doc.file_size == 1024
    assert doc.status == "ready"
    assert doc.chunk_count == 5
    assert doc.error_message is None
    assert doc.created_at is not None
    assert doc.updated_at is not None


@pytest.mark.asyncio
async def test_knowledge_document_defaults(async_db_session: AsyncSession):
    """Verify default values for chunk_count and status."""
    doc = KnowledgeDocument(
        tenant_id=1,
        filename="defaults_test.txt",
        content_type="text/plain",
        file_size=512,
    )
    async_db_session.add(doc)
    await async_db_session.flush()
    await async_db_session.refresh(doc)

    assert doc.status == "uploading"  # default
    assert doc.chunk_count == 0  # default
    assert doc.error_message is None


@pytest.mark.asyncio
async def test_knowledge_document_error_status(async_db_session: AsyncSession):
    """Set status to 'error' with an error message."""
    doc = KnowledgeDocument(
        tenant_id=1,
        filename="broken.pdf",
        content_type="application/pdf",
        file_size=99999,
        status="error",
        error_message="Failed to parse PDF: corrupt file",
    )
    async_db_session.add(doc)
    await async_db_session.flush()
    await async_db_session.refresh(doc)

    assert doc.status == "error"
    assert doc.error_message == "Failed to parse PDF: corrupt file"


@pytest.mark.asyncio
async def test_knowledge_document_query_by_tenant(async_db_session: AsyncSession):
    """Query documents filtered by tenant_id."""
    for i in range(3):
        async_db_session.add(
            KnowledgeDocument(
                tenant_id=1,
                filename=f"doc_{i}.txt",
                content_type="text/plain",
                file_size=100,
            )
        )
    async_db_session.add(
        KnowledgeDocument(
            tenant_id=2,
            filename="other_tenant.txt",
            content_type="text/plain",
            file_size=200,
        )
    )
    await async_db_session.flush()

    result = await async_db_session.execute(
        select(KnowledgeDocument).where(KnowledgeDocument.tenant_id == 1)
    )
    docs = list(result.scalars().all())
    assert len(docs) == 3
    assert all(d.tenant_id == 1 for d in docs)
