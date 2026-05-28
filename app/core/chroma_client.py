"""ChromaDB client with lazy import for SQLite compatibility."""

from app.config import settings

_collection = None


def get_collection():
    """Get or create the ChromaDB persistent collection."""
    global _collection
    if _collection is None:
        import chromadb

        client = chromadb.PersistentClient(path=settings.chroma_db_path)
        _collection = client.get_or_create_collection("company_memory")
    return _collection
