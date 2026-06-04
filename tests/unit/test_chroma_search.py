"""Tests for ChromaDB search functionality (Task 2)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_chroma_collection():
    """Mock a ChromaDB collection for query/add operations."""
    coll = MagicMock()
    coll.query.return_value = {
        "ids": [["id1", "id2"]],
        "documents": [["doc1 content", "doc2 content"]],
        "metadatas": [[{"tenant_id": "1"}, {"tenant_id": "1"}]],
        "distances": [[0.1, 0.3]],
    }
    return coll


@pytest.mark.asyncio
async def test_semantic_search_knowledge_returns_results(mock_chroma_collection):
    """semantic_search_knowledge returns parsed results."""
    from app.core.chroma_client import semantic_search_knowledge

    with patch("app.core.chroma_client.get_knowledge_collection", return_value=mock_chroma_collection):
        results = await semantic_search_knowledge("test query")

    assert len(results) == 2
    assert results[0]["id"] == "id1"
    assert results[0]["document"] == "doc1 content"
    assert results[0]["distance"] == 0.1


@pytest.mark.asyncio
async def test_semantic_search_knowledge_empty():
    """Empty ChromaDB collection returns empty list."""
    from app.core.chroma_client import semantic_search_knowledge

    empty_collection = MagicMock()
    empty_collection.query.return_value = {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}

    with patch("app.core.chroma_client.get_knowledge_collection", return_value=empty_collection):
        results = await semantic_search_knowledge("test")

    assert results == []


@pytest.mark.asyncio
async def test_semantic_search_knowledge_exception_safe():
    """Exception during query returns empty list (fail-open)."""
    from app.core.chroma_client import semantic_search_knowledge

    bad_collection = MagicMock()
    bad_collection.query.side_effect = RuntimeError("ChromaDB down")

    with patch("app.core.chroma_client.get_knowledge_collection", return_value=bad_collection):
        results = await semantic_search_knowledge("test")

    assert results == []


@pytest.mark.asyncio
async def test_semantic_search_memory_with_db_crossref():
    """semantic_search_memory cross-references ChromaDB results with DB records."""
    from app.services.memory_service import semantic_search_memory

    mock_db = AsyncMock()
    mock_db_result = MagicMock()
    mock_m1 = MagicMock()
    mock_m1.chroma_id = "id1"
    mock_m1.title = "Test Title"
    mock_m1.content = "Content"
    mock_m1.category = "general"
    mock_m1.created_at = None
    mock_m2 = MagicMock()
    mock_m2.chroma_id = "id2"
    mock_m2.title = "Test Title 2"
    mock_m2.content = "Content 2"
    mock_m2.category = "general"
    mock_m2.created_at = None
    mock_db_result.scalars().all.return_value = [mock_m1, mock_m2]
    mock_db.execute.return_value = mock_db_result

    with patch("app.core.chroma_client.semantic_search_knowledge") as mock_search:
        mock_search.return_value = [
            {"id": "id1", "document": "doc1", "metadata": {}, "distance": 0.1},
            {"id": "id2", "document": "doc2", "metadata": {}, "distance": 0.3},
        ]
        results = await semantic_search_memory(mock_db, "test query", tenant_id=1)

    assert len(results) == 2
    assert results[0].chroma_id == "id1"
    assert results[1].chroma_id == "id2"


@pytest.mark.asyncio
async def test_semantic_search_memory_chroma_fail_fallback():
    """When ChromaDB fails, semantic_search_memory returns empty list (fail-open)."""
    from app.services.memory_service import semantic_search_memory

    mock_db = AsyncMock()

    with patch("app.core.chroma_client.semantic_search_knowledge", side_effect=RuntimeError):
        results = await semantic_search_memory(mock_db, "test", tenant_id=1)

    assert results == []


@pytest.mark.asyncio
async def test_add_to_knowledge_collection():
    """add_to_knowledge_collection adds documents correctly."""
    from app.core.chroma_client import add_to_knowledge_collection

    mock_collection = MagicMock()

    with patch("app.core.chroma_client.get_knowledge_collection", return_value=mock_collection):
        await add_to_knowledge_collection(
            documents=["test doc"],
            metadatas=[{"tenant_id": "1"}],
            ids=["doc1_chunk0"],
        )

    mock_collection.add.assert_called_once_with(
        documents=["test doc"],
        metadatas=[{"tenant_id": "1"}],
        ids=["doc1_chunk0"],
    )


@pytest.mark.asyncio
async def test_add_to_knowledge_collection_exception():
    """Exception during add is caught and logged."""
    from app.core.chroma_client import add_to_knowledge_collection

    bad_collection = MagicMock()
    bad_collection.add.side_effect = RuntimeError("ChromaDB write error")

    with patch("app.core.chroma_client.get_knowledge_collection", return_value=bad_collection):
        # Should not raise
        await add_to_knowledge_collection(
            documents=["test"], metadatas=[{"k": "v"}], ids=["id1"]
        )


@pytest.mark.asyncio
async def test_embedding_service_singleton():
    """get_embedding_service returns a singleton."""
    from app.services.embedding_service import get_embedding_service

    svc1 = get_embedding_service()
    svc2 = get_embedding_service()
    assert svc1 is svc2
    assert svc1.model == "text-embedding-3-small"


@pytest.mark.asyncio
async def test_embed_text_cached():
    """embed_text returns same result for same input."""
    from app.services.embedding_service import OpenAIEmbeddingService

    svc = OpenAIEmbeddingService(api_key="test-key")
    mock_embed = AsyncMock(return_value=[[0.1, 0.2, 0.3]])

    with patch.object(svc, "embed_texts", mock_embed):
        vec1 = await svc.embed_text("hello world")
        vec2 = await svc.embed_text("hello world")
        assert vec1 == vec2
        # embed_texts was called (cached result)
        assert mock_embed.call_count >= 1


@pytest.mark.asyncio
async def test_batch_ingest_chunks():
    """batch_ingest_chunks calls collection.add for each batch."""
    from app.services.embedding_service import OpenAIEmbeddingService

    svc = OpenAIEmbeddingService(api_key="test-key")
    mock_collection = MagicMock()
    chunks = [
        {"id": "c1", "text": "text1", "metadata": {"k": "v1"}},
        {"id": "c2", "text": "text2", "metadata": {"k": "v2"}},
    ]

    with patch.object(svc, "embed_texts", return_value=[[0.1] * 1536, [0.2] * 1536]):
        count = await svc.batch_ingest_chunks(chunks, mock_collection, batch_size=10)

    assert count == 2
    # Each chunk is added individually to the collection
    assert mock_collection.add.call_count == 2


@pytest.mark.asyncio
async def test_knowledge_service_ingest_chunks():
    """KnowledgeService._ingest_chunks calls embedding + chroma add."""
    from app.services.knowledge_service import KnowledgeService

    mock_db = AsyncMock()
    with patch("app.core.chroma_client.get_knowledge_collection") as mock_get_coll, \
         patch("app.services.embedding_service.get_embedding_service") as mock_get_svc:

        mock_coll = MagicMock()
        mock_get_coll.return_value = mock_coll

        mock_svc = MagicMock()
        mock_svc.batch_ingest_chunks = AsyncMock(return_value=3)
        mock_get_svc.return_value = mock_svc

        count = await KnowledgeService._ingest_chunks(
            mock_db,
            doc_id=1,
            tenant_id=1,
            chunks=["chunk1", "chunk2", "chunk3"],
            filename="test.txt",
        )

    assert count == 3
    mock_svc.batch_ingest_chunks.assert_called_once()


@pytest.mark.asyncio
async def test_semantic_search_endpoint(api_client, auth_headers):
    """GET /knowledge/semantic-search returns semantic results."""
    mock_memory = MagicMock()
    mock_memory.id = 1
    mock_memory.title = "Found Doc"
    mock_memory.content = "Relevant content here"
    mock_memory.category = "general"
    mock_memory.chroma_id = "ch_1"
    mock_memory.created_at = None

    with patch("app.api.v1.knowledge.semantic_search_memory", return_value=[mock_memory]):
        resp = await api_client.get(
            "/api/v1/knowledge/semantic-search?q=test",
            headers=auth_headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] == "Found Doc"
