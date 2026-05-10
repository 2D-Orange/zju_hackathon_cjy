import os

from app.services.textbook_store import TextbookStore

# Singleton store shared across all API routers
_store: TextbookStore | None = None


def get_store() -> TextbookStore:
    global _store
    if _store is None:
        _store = TextbookStore(upload_dir=os.getenv("UPLOAD_DIR", "data/uploads"))
    return _store