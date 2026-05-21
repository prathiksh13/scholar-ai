"""In-memory + file persistence for FormatFlow documents."""

import json
from pathlib import Path

from app.config import UPLOAD_DIR
from app.models.document_schema import SemanticDocument
from app.services.compliance import ComplianceReport
from app.rules.ieee import FormatAction

_records: dict[str, dict] = {}
_semantic: dict[str, SemanticDocument] = {}
_formatted: dict[str, SemanticDocument] = {}
_compliance: dict[str, ComplianceReport] = {}
_actions: dict[str, list] = {}


def create_record(document_id: str, file_path: str, filename: str) -> dict:
    record = {
        "id": document_id,
        "file_path": file_path,
        "filename": filename,
        "output_path": None,
        "editor_dirty": False,
    }
    _records[document_id] = record
    _save_meta(document_id, record)
    return record


def get_record(document_id: str) -> dict | None:
    if document_id in _records:
        return _records[document_id]
    meta = UPLOAD_DIR / f"ff_{document_id}.json"
    if meta.exists():
        data = json.loads(meta.read_text(encoding="utf-8"))
        _records[document_id] = data
        return data
    return None


def save_semantic(document_id: str, doc: SemanticDocument) -> None:
    _semantic[document_id] = doc
    path = UPLOAD_DIR / f"ff_{document_id}_semantic.json"
    path.write_text(doc.model_dump_json(), encoding="utf-8")


def get_semantic(document_id: str) -> SemanticDocument | None:
    if document_id in _semantic:
        return _semantic[document_id]
    path = UPLOAD_DIR / f"ff_{document_id}_semantic.json"
    if path.exists():
        doc = SemanticDocument.model_validate_json(path.read_text(encoding="utf-8"))
        _semantic[document_id] = doc
        return doc
    return None


def save_formatted(document_id: str, doc: SemanticDocument, actions: list[FormatAction]) -> None:
    _formatted[document_id] = doc
    _actions[document_id] = actions
    rec = get_record(document_id) or {}
    rec["editor_dirty"] = False
    _records[document_id] = rec
    _save_meta(document_id, rec)
    path = UPLOAD_DIR / f"ff_{document_id}_formatted.json"
    path.write_text(doc.model_dump_json(), encoding="utf-8")


def get_formatted(document_id: str) -> SemanticDocument | None:
    if document_id in _formatted:
        return _formatted[document_id]
    path = UPLOAD_DIR / f"ff_{document_id}_formatted.json"
    if path.exists():
        doc = SemanticDocument.model_validate_json(path.read_text(encoding="utf-8"))
        _formatted[document_id] = doc
        return doc
    return get_semantic(document_id)


def save_compliance(document_id: str, report: ComplianceReport) -> None:
    _compliance[document_id] = report


def get_compliance(document_id: str) -> ComplianceReport | None:
    return _compliance.get(document_id)


def set_output_path(document_id: str, path: str) -> None:
    rec = get_record(document_id)
    if rec:
        rec["output_path"] = path
        _records[document_id] = rec
        _save_meta(document_id, rec)


def update_formatted_html(document_id: str, html: str) -> None:
    rec = get_record(document_id) or {}
    rec["editor_html"] = html
    formatted = get_formatted(document_id)
    rec["editor_dirty"] = bool(not formatted or html.strip() != formatted.to_editor_html().strip())
    _records[document_id] = rec
    _save_meta(document_id, rec)


def get_editor_html(document_id: str) -> str | None:
    rec = get_record(document_id)
    if rec and rec.get("editor_html"):
        return rec["editor_html"]
    fmt = get_formatted(document_id)
    return fmt.to_editor_html() if fmt else None


def is_editor_dirty(document_id: str) -> bool:
    rec = get_record(document_id)
    return bool(rec and rec.get("editor_dirty"))


def _save_meta(document_id: str, data: dict) -> None:
    path = UPLOAD_DIR / f"ff_{document_id}.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
