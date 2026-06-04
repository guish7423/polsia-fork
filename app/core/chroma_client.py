"""ChromaDB client with lazy import for SQLite compatibility and RAG support."""

from app.config import settings

_collection = None
_knowledge_collection = None


def get_collection():
    """Get or create the company_memory ChromaDB collection."""
    global _collection
    if _collection is None:
        import chromadb

        client = chromadb.PersistentClient(path=settings.chroma_db_path)
        _collection = client.get_or_create_collection("company_memory")
    return _collection


def get_knowledge_collection():
    """Get or create the knowledge_base ChromaDB collection for RAG."""
    global _knowledge_collection
    if _knowledge_collection is None:
        import chromadb

        client = chromadb.PersistentClient(path=settings.chroma_db_path)
        _knowledge_collection = client.get_or_create_collection("knowledge_base")
    return _knowledge_collection


async def add_to_knowledge_collection(
    documents: list[str],
    metadatas: list[dict],
    ids: list[str],
) -> None:
    """Add documents to the knowledge_base ChromaDB collection.

    Uses embeddings directly — callers should embed first.
    """
    collection = get_knowledge_collection()
    try:
        collection.add(documents=documents, metadatas=metadatas, ids=ids)
    except Exception as exc:
        import logging

        logger = logging.getLogger(__name__)
        logger.error("ChromaDB add failed: %s", exc)


async def semantic_search_knowledge(
    query: str,
    n_results: int = 5,
    filter_tenant: int | None = None,
) -> list[dict]:
    """Vector similarity search over the knowledge_base collection.

    Returns a list of dicts with ``id``, ``document``, ``metadata``, ``distance``.
    """
    collection = get_knowledge_collection()
    try:
        where = {"tenant_id": str(filter_tenant)} if filter_tenant is not None else None
        results = collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where,
        )
    except Exception:
        return []

    # Flatten results into list of dicts
    output: list[dict] = []
    if not results or not results.get("ids"):
        return output

    for i, doc_id in enumerate(results["ids"][0]):
        output.append({
            "id": doc_id,
            "document": results["documents"][0][i] if results.get("documents") else "",
            "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
            "distance": results["distances"][0][i] if results.get("distances") else 0.0,
        })

    return output
