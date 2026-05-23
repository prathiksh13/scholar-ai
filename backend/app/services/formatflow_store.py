"""In-memory + file persistence for FormatFlow documents."""

import json
from pathlib import Path

from app.config import TEX_DIR, UPLOAD_DIR
from app.models.document_schema import SemanticDocument
from app.services.compliance import ComplianceReport
from app.rules.ieee import FormatAction

_records: dict[str, dict] = {}
_semantic: dict[str, SemanticDocument] = {}
_formatted: dict[str, SemanticDocument] = {}
_compliance: dict[str, ComplianceReport] = {}
_actions: dict[str, list] = {}
_latex: dict[str, str] = {}
_compile_errors: dict[str, list[dict]] = {}


def create_record(document_id: str, file_path: str, filename: str) -> dict:
    record = {
        "id": document_id,
        "file_path": file_path,
        "filename": filename,
        "output_path": None,
        "editor_dirty": False,
        "latex_path": None,
        "pdf_path": None,
        "compile_errors": [],
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


def save_latex(document_id: str, tex: str) -> None:
    _latex[document_id] = tex
    rec = get_record(document_id) or {}
    rec["latex_path"] = str((TEX_DIR / document_id / "paper.tex").resolve())
    _records[document_id] = rec
    _save_meta(document_id, rec)
    (TEX_DIR / document_id).mkdir(parents=True, exist_ok=True)
    (TEX_DIR / document_id / "paper.tex").write_text(tex, encoding="utf-8")


def get_latex(document_id: str) -> str | None:
    if document_id in _latex:
        return _latex[document_id]
    path = TEX_DIR / document_id / "paper.tex"
    if path.exists():
        tex = path.read_text(encoding="utf-8")
        _latex[document_id] = tex
        return tex
    return None


def save_compile_errors(document_id: str, errors: list[dict]) -> None:
    _compile_errors[document_id] = errors
    rec = get_record(document_id) or {}
    rec["compile_errors"] = errors
    _records[document_id] = rec
    _save_meta(document_id, rec)


def get_compile_errors(document_id: str) -> list[dict]:
    if document_id in _compile_errors:
        return _compile_errors[document_id]
    rec = get_record(document_id) or {}
    return rec.get("compile_errors", []) or []


def save_pdf_path(document_id: str, pdf_path: str) -> None:
    rec = get_record(document_id) or {}
    rec["pdf_path"] = pdf_path
    _records[document_id] = rec
    _save_meta(document_id, rec)


def get_pdf_path(document_id: str) -> str | None:
    rec = get_record(document_id) or {}
    return rec.get("pdf_path")


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
