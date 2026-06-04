"""Knowledge Base API routes — document upload, CRUD, and search."""

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import verify_api_key
from app.core.database import get_db
from app.core.tenant_context import get_current_tenant
from app.services.knowledge_service import KnowledgeService
from app.services.memory_service import semantic_search_memory

router = APIRouter(tags=["knowledge"])


# ─── Tenant ID dependency ────────────────────────────────────────────────


async def _get_tenant_id() -> int:
    """Extract tenant ID from the current request context."""
    tenant = get_current_tenant()
    if tenant is None:
        return 0
    return tenant.id


# ─── Helper: serialize document to dict ──────────────────────────────────


def _doc_to_dict(doc) -> dict:
    return {
        "id": doc.id,
        "tenant_id": doc.tenant_id,
        "filename": doc.filename,
        "content_type": doc.content_type,
        "file_size": doc.file_size,
        "status": doc.status,
        "chunk_count": doc.chunk_count,
        "error_message": doc.error_message,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
        "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
    }


# ─── Endpoints ───────────────────────────────────────────────────────────


@router.post("/knowledge/upload", status_code=201)
async def upload_document(
    file: UploadFile,
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(_get_tenant_id),
):
    """Upload a document file. Supports TXT, MD, PDF, and other text formats."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    # Validate content type
    content_type = file.content_type or "application/octet-stream"

    # Read file content
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    # Process the upload (parse, chunk, store)
    doc = await KnowledgeService.process_upload(
        db,
        tenant_id=tenant_id,
        filename=file.filename,
        content_type=content_type,
        content=content,
    )

    if doc.status == "error":
        raise HTTPException(
            status_code=400,
            detail=f"Failed to process document: {doc.error_message}",
        )

    return _doc_to_dict(doc)


@router.get("/knowledge/documents")
async def list_documents(
    status: str | None = Query(default=None),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(_get_tenant_id),
):
    """List all documents for the current tenant, with optional status filter."""
    docs = await KnowledgeService.list_documents(
        db, tenant_id=tenant_id, status=status, limit=limit, offset=offset
    )
    return [_doc_to_dict(d) for d in docs]


@router.get("/knowledge/documents/{doc_id}")
async def get_document(
    doc_id: int,
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(_get_tenant_id),
):
    """Get a single document by ID."""
    doc = await KnowledgeService.get_document(db, doc_id=doc_id, tenant_id=tenant_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return _doc_to_dict(doc)


@router.delete("/knowledge/documents/{doc_id}", status_code=204)
async def delete_document(
    doc_id: int,
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(_get_tenant_id),
):
    """Soft-delete a document by ID."""
    deleted = await KnowledgeService.soft_delete_document(
        db, doc_id=doc_id, tenant_id=tenant_id
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    return None


@router.get("/knowledge/search")
async def search_documents(
    q: str = Query(..., min_length=1),
    limit: int = Query(default=20, le=100),
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(_get_tenant_id),
):
    """Search documents by filename keyword (SQL LIKE fallback)."""
    docs = await KnowledgeService.search_documents(
        db, tenant_id=tenant_id, query=q, limit=limit
    )
    return [_doc_to_dict(d) for d in docs]


@router.get("/knowledge/semantic-search")
async def semantic_search(
    q: str = Query(..., min_length=1),
    limit: int = Query(default=5, le=20),
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
    tenant_id: int = Depends(_get_tenant_id),
):
    """Semantic search over knowledge base via vector similarity."""
    results = await semantic_search_memory(
        db, query=q, tenant_id=tenant_id, n_results=limit
    )
    return [
        {
            "id": r.id,
            "title": r.title,
            "content": r.content[:500],
            "category": r.category,
            "chroma_id": r.chroma_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in results
    ]
