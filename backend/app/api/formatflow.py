import uuid
from pathlib import Path
import re

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, BackgroundTasks, Request
import asyncio
import aiofiles
import os
from fastapi.responses import FileResponse, StreamingResponse
from fastapi import Query
from pydantic import BaseModel

from app.auth import get_current_user
from app.config import UPLOAD_DIR
from app.models.document_schema import Author, DocumentElement, SemanticDocument
from app.rules.ieee import FormatAction
from app.services.compliance import run_compliance_check
from app.services.format_pipeline import stream_format_job
from app.services.formatflow_store import (
    create_record,
    get_compile_errors,
    get_compliance,
    get_editor_html,
    get_formatted,
    get_latex,
    get_pdf_path,
    get_record,
    get_semantic,
    is_editor_dirty,
    save_compile_errors,
    save_latex,
    save_formatted,
    save_semantic,
    save_compliance,
    save_pdf_path,
    update_formatted_html,
)
from app.services.latex_service import compile_latex, latex_to_semantic, semantic_to_latex, write_latex_bundle
from app.services.renderer import render_editor_html_to_docx, render_semantic_to_docx, render_semantic_to_pdf
from app.services.semantic_parser import new_document_id, parse_document_to_semantic

router = APIRouter(prefix="/formatflow", tags=["FormatFlow"])


class FormatStartRequest(BaseModel):
    document_id: str
    format: str = "IEEE"


class DocumentUpdateRequest(BaseModel):
    html: str


class SemanticUpdateRequest(BaseModel):
    semantic: SemanticDocument


@router.post("/upload")
async def upload_docx(
    background_tasks: BackgroundTasks,
    request: Request,
    file: UploadFile = File(...),
):
    print("Upload request received")
    try:
        print(f"Client: {request.client.host if request.client else 'unknown'}")
        print(f"Content-Length: {request.headers.get('content-length')}")
        print(f"Content-Type: {request.headers.get('content-type')}")
        if not file.filename or not file.filename.lower().endswith((".docx", ".pdf")):
            raise HTTPException(status_code=400, detail="MVP supports .docx and .pdf only")

        document_id = new_document_id()
        suffix = Path(file.filename).suffix.lower() or ".docx"
        save_path = UPLOAD_DIR / f"{document_id}{suffix}"

        # ensure uploads dir exists
        os.makedirs(UPLOAD_DIR, exist_ok=True)

        print("Saving uploaded file:", file.filename)
        # write to disk in chunks to avoid big memory pressure
        try:
            async with aiofiles.open(save_path, "wb") as out:
                while True:
                    chunk = await file.read(1024 * 1024)
                    if not chunk:
                        break
                    await out.write(chunk)
        except Exception as e:
            print("Error saving upload:", e)
            raise HTTPException(status_code=500, detail=f"Could not save upload: {e}") from e

        create_record(document_id, str(save_path), file.filename)

        # schedule parsing in background (offload CPU work to thread)
        async def _parse_and_save(doc_id: str, path: str, filename: str):
            try:
                print(f"Background parse started for {doc_id}")
                semantic = await asyncio.to_thread(parse_document_to_semantic, Path(path), doc_id, filename)
                from app.services.formatflow_store import save_semantic

                save_semantic(doc_id, semantic)
                tex_path = write_latex_bundle(doc_id, semantic)
                save_latex(doc_id, tex_path.read_text(encoding="utf-8"))
                pdf_path, errors = compile_latex(tex_path)
                save_compile_errors(doc_id, errors)
                if pdf_path:
                    save_pdf_path(doc_id, str(pdf_path))
                print(f"Background parse complete for {doc_id}")
            except Exception as e:
                import traceback

                print("Background parsing error:", e)
                traceback.print_exc()

        background_tasks.add_task(_parse_and_save, document_id, str(save_path), file.filename)

        return {
            "success": True,
            "document_id": document_id,
            "filename": file.filename,
            "message": "Upload received, parsing in background",
        }

    except HTTPException:
        raise
    except Exception as e:
        print("Unexpected upload error:", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/documents/{document_id}")
async def get_document(
    document_id: str,
    user: dict = Depends(get_current_user),
):
    rec = get_record(document_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Document not found")

    semantic = get_semantic(document_id)
    formatted = get_formatted(document_id)
    compliance = get_compliance(document_id)

    return {
        "document_id": document_id,
        "filename": rec.get("filename", ""),
        "semantic": semantic.model_dump() if semantic else None,
        "original_html": semantic.to_editor_html() if semantic else "",
        "formatted_html": get_editor_html(document_id) or (formatted.to_editor_html() if formatted else ""),
        "compliance": compliance.model_dump() if compliance else None,
        "latex": get_latex(document_id) or "",
        "compile_errors": get_compile_errors(document_id),
        "pdf_path": get_pdf_path(document_id),
    }


@router.post("/format/stream")
async def format_stream(
    body: FormatStartRequest,
    user: dict = Depends(get_current_user),
):
    if not get_record(body.document_id):
        raise HTTPException(status_code=404, detail="Document not found")

    return StreamingResponse(
        stream_format_job(body.document_id, body.format),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/compliance/{document_id}")
async def compliance(
    document_id: str,
    user: dict = Depends(get_current_user),
):
    doc = get_formatted(document_id) or get_semantic(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    report = get_compliance(document_id) or run_compliance_check(doc)
    return report.model_dump()


@router.patch("/documents/{document_id}")
async def update_document(
    document_id: str,
    body: DocumentUpdateRequest,
    user: dict = Depends(get_current_user),
):
    if not get_record(document_id):
        raise HTTPException(status_code=404, detail="Document not found")

    base_doc = get_formatted(document_id) or get_semantic(document_id)
    if not base_doc:
        update_formatted_html(document_id, body.html)
        return {"ok": True, "formatted_html": body.html}

    try:
        reflowed = _semantic_from_layout_html(base_doc, body.html)
        reflowed.id = document_id
        reflowed.filename = base_doc.filename
        reflowed.metadata = dict(base_doc.metadata)

        save_semantic(document_id, reflowed)
        save_formatted(document_id, reflowed, actions=[])

        tex_path = write_latex_bundle(document_id, reflowed)
        save_latex(document_id, tex_path.read_text(encoding="utf-8"))
        pdf_path, compile_errors = compile_latex(tex_path)
        save_compile_errors(document_id, compile_errors)
        if pdf_path:
            save_pdf_path(document_id, str(pdf_path))

        compliance = run_compliance_check(reflowed)
        save_compliance(document_id, compliance)

        refreshed_html = reflowed.to_editor_html()
        update_formatted_html(document_id, refreshed_html)
        return {
            "ok": True,
            "formatted_html": refreshed_html,
            "semantic": reflowed.model_dump(),
            "compliance": compliance.model_dump(),
            "latex": get_latex(document_id) or tex_path.read_text(encoding="utf-8"),
            "compile_errors": compile_errors,
        }
    except Exception:
        update_formatted_html(document_id, body.html)
        return {"ok": True, "formatted_html": body.html}


@router.get("/documents/{document_id}/latex")
async def get_latex_source(document_id: str, user: dict = Depends(get_current_user)):
    if not get_record(document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    return {
        "document_id": document_id,
        "latex": get_latex(document_id) or "",
        "compile_errors": get_compile_errors(document_id),
        "pdf_path": get_pdf_path(document_id),
    }


class LatexUpdateRequest(BaseModel):
    latex: str


@router.patch("/documents/{document_id}/latex")
async def update_latex_source(document_id: str, body: LatexUpdateRequest, user: dict = Depends(get_current_user)):
    rec = get_record(document_id)
    semantic = get_semantic(document_id)
    if not rec or not semantic:
        raise HTTPException(status_code=404, detail="Document not found")

    save_latex(document_id, body.latex)
    next_semantic = latex_to_semantic(body.latex, semantic)
    save_semantic(document_id, next_semantic)
    save_formatted(document_id, next_semantic, actions=[])
    update_formatted_html(document_id, next_semantic.to_editor_html())

    tex_path = write_latex_bundle(document_id, next_semantic)
    tex_path.write_text(body.latex, encoding="utf-8")
    pdf_path, compile_errors = compile_latex(tex_path)
    save_compile_errors(document_id, compile_errors)
    if pdf_path:
        save_pdf_path(document_id, str(pdf_path))

    return {
        "ok": True,
        "latex": body.latex,
        "semantic": next_semantic.model_dump(),
        "compile_errors": compile_errors,
        "pdf_path": str(pdf_path) if pdf_path else None,
    }


@router.post("/documents/{document_id}/latex/compile")
async def compile_latex_source(document_id: str, user: dict = Depends(get_current_user)):
    rec = get_record(document_id)
    semantic = get_semantic(document_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Document not found")
    tex = get_latex(document_id)
    if not tex:
        raise HTTPException(status_code=404, detail="LaTeX source not found")
    if not semantic:
        raise HTTPException(status_code=404, detail="Semantic document not found")
    tex_path = write_latex_bundle(document_id, semantic)
    tex_path.write_text(tex, encoding="utf-8")
    pdf_path, compile_errors = compile_latex(tex_path)
    save_compile_errors(document_id, compile_errors)
    if pdf_path:
        save_pdf_path(document_id, str(pdf_path))
    return {
        "ok": True,
        "compile_errors": compile_errors,
        "pdf_path": str(pdf_path) if pdf_path else None,
    }


@router.get("/documents/{document_id}/pdf")
async def get_compiled_pdf(document_id: str, user: dict = Depends(get_current_user)):
    pdf_path = get_pdf_path(document_id)
    if not pdf_path or not Path(pdf_path).exists():
        raise HTTPException(status_code=404, detail="Compiled PDF not found")
    return FileResponse(pdf_path, media_type="application/pdf", filename=f"{document_id}.pdf")


@router.patch("/documents/{document_id}/semantic")
async def update_semantic_document(
    document_id: str,
    body: SemanticUpdateRequest,
    user: dict = Depends(get_current_user),
):
    rec = get_record(document_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Document not found")

    semantic = body.semantic
    semantic.id = document_id
    semantic.filename = rec.get("filename", semantic.filename)
    from app.services.formatflow_store import save_semantic

    save_semantic(document_id, semantic)
    update_formatted_html(document_id, semantic.to_editor_html())

    return {
        "ok": True,
        "semantic": semantic.model_dump(),
        "formatted_html": semantic.to_editor_html(),
    }


def _semantic_from_layout_html(base_doc: SemanticDocument, html: str) -> SemanticDocument:
    from lxml import etree

    root = etree.HTML(html)
    if root is None:
        return base_doc

    blocks: list[DocumentElement] = []
    order = 0
    for node in root.xpath('.//div[contains(@class, "layout-block") and @data-block-kind]'):
        kind = (node.get('data-block-kind') or '').strip().lower()
        text = ''.join(node.xpath('.//text()')).strip()

        if kind in {"title", "author", "keyword", "heading", "paragraph", "references", "reference"}:
            mapped = "heading" if kind == "references" else kind
            blocks.append(DocumentElement(type=mapped, content=_normalize_text(text), order=order, level=1))
            order += 1
            continue

        if kind == "figure":
            img_src = _first_or_none(node.xpath('.//img/@src'))
            caption = _normalize_text(''.join(node.xpath('.//figcaption//text()')).strip())
            width_pct = _width_pct_from_style(node.get('style'))
            blocks.append(
                DocumentElement(
                    type="figure",
                    content=caption,
                    caption=caption,
                    src=img_src,
                    width_pct=width_pct,
                    order=order,
                )
            )
            order += 1
            continue

        if kind == "table":
            rows: list[list[str]] = []
            for tr in node.xpath('.//tr'):
                cells = [_normalize_text(''.join(cell.xpath('.//text()'))) for cell in tr.xpath('./th|./td')]
                if any(cells):
                    rows.append(cells)
            caption = _normalize_text(''.join(node.xpath('.//figcaption//text()')).strip())
            width_pct = _width_pct_from_style(node.get('style'))
            blocks.append(
                DocumentElement(
                    type="table",
                    content=caption or "Table",
                    caption=caption,
                    rows=rows,
                    width_pct=width_pct,
                    order=order,
                )
            )
            order += 1

    title = base_doc.title
    authors = list(base_doc.authors)
    abstract = base_doc.abstract
    keywords = list(base_doc.keywords)

    title_block = next((block for block in blocks if block.type == "title" and block.content), None)
    if title_block:
        title = title_block.content

    author_blocks = [block.content for block in blocks if block.type == "author" and block.content]
    if author_blocks:
        joined = ', '.join(author_blocks)
        authors = [Author(name=name.strip()) for name in re.split(r',| and ', joined) if name.strip()]

    keyword_block = next((block for block in blocks if block.type == "keyword" and block.content), None)
    if keyword_block:
        keyword_text = re.sub(r'^keywords?\s*:\s*', '', keyword_block.content, flags=re.I)
        keywords = [item.strip() for item in re.split(r',|;', keyword_text) if item.strip()]

    abstract_parts: list[str] = []
    in_abstract = False
    for block in blocks:
        if block.type == "heading" and block.content.strip().lower() == "abstract":
            in_abstract = True
            continue
        if in_abstract and block.type == "heading":
            break
        if in_abstract and block.type == "paragraph" and block.content:
            abstract_parts.append(block.content)
    if abstract_parts:
        abstract = ' '.join(abstract_parts)

    references_started = False
    deduped_blocks: list[DocumentElement] = []
    seen_ref: set[str] = set()
    for block in blocks:
        if block.type == "heading" and block.content.strip().lower() == "references":
            references_started = True
            deduped_blocks.append(block)
            continue
        if references_started and block.type == "reference":
            key = block.content.strip().lower()
            if key and key not in seen_ref:
                seen_ref.add(key)
                deduped_blocks.append(block)
            continue
        deduped_blocks.append(block)

    return SemanticDocument(
        id=base_doc.id,
        filename=base_doc.filename,
        format_target=base_doc.format_target,
        title=title,
        authors=authors,
        abstract=abstract,
        keywords=keywords,
        sections=base_doc.sections,
        figures=base_doc.figures,
        tables=base_doc.tables,
        references=base_doc.references,
        elements=deduped_blocks,
        metadata=dict(base_doc.metadata),
    )


def _normalize_text(value: str) -> str:
    return re.sub(r'\s+', ' ', value or '').strip()


def _first_or_none(values: list[str]) -> str | None:
    return values[0] if values else None


def _width_pct_from_style(style: str | None) -> float | None:
    if not style:
        return None
    match = re.search(r'width\s*:\s*([\d.]+)pt', style, flags=re.I)
    if not match:
        return None
    width_pt = float(match.group(1))
    # Approximate relative width to IEEE column width (~252pt).
    return max(30.0, min(100.0, (width_pt / 252.0) * 100.0))


@router.get("/export/{document_id}")
async def export_docx(
    document_id: str,
    kind: str = Query(default="docx", pattern="^(docx|pdf)$"),
    user: dict = Depends(get_current_user),
):
    rec = get_record(document_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Export not ready — run formatting first")

    if kind == "pdf":
        semantic = get_formatted(document_id) or get_semantic(document_id)
        if not semantic:
            raise HTTPException(status_code=404, detail="Export not ready - run formatting first")
        path = render_semantic_to_pdf(semantic, document_id)
    else:
        semantic = get_formatted(document_id) or get_semantic(document_id)
        if semantic and not is_editor_dirty(document_id):
            path = render_semantic_to_docx(semantic, document_id)
        else:
            editor_html = get_editor_html(document_id)
            path = render_editor_html_to_docx(editor_html, document_id) if editor_html else None
            if not path:
                if not rec.get("output_path"):
                    raise HTTPException(status_code=404, detail="Export not ready - run formatting first")
                path = Path(rec["output_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Export file missing")
    media_type = (
        "application/pdf"
        if kind == "pdf"
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    filename = f"formatflow_{document_id[:8]}.{kind}"
    return FileResponse(
        path=str(path),
        media_type=media_type,
        filename=filename,
    )
