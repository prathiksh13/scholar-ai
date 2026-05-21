import json
import uuid
from pathlib import Path

from app.config import UPLOAD_DIR

_registry: dict[str, dict] = {}


def create_document(original_path: Path, text: str, filename: str) -> str:
    doc_id = str(uuid.uuid4())
    meta = {
        "id": doc_id,
        "filename": filename,
        "original_path": str(original_path),
        "text": text,
        "format": None,
        "preview_html": "",
    }
    _registry[doc_id] = meta
    _save_meta(doc_id, meta)
    return doc_id


def get_document(doc_id: str) -> dict | None:
    if doc_id in _registry:
        return _registry[doc_id]
    meta_path = UPLOAD_DIR / f"{doc_id}.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        _registry[doc_id] = meta
        return meta
    return None


def update_document(doc_id: str, **kwargs) -> dict | None:
    doc = get_document(doc_id)
    if not doc:
        return None
    doc.update(kwargs)
    _registry[doc_id] = doc
    _save_meta(doc_id, doc)
    return doc


def _save_meta(doc_id: str, meta: dict) -> None:
    path = UPLOAD_DIR / f"{doc_id}.json"
    path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
