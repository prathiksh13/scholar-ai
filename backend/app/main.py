import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.api.formatflow import router as formatflow_router
from app.auth import get_current_user
from app.config import OUTPUT_DIR, UPLOAD_DIR
from app.schemas import AiSuggestionsRequest, ConvertRequest, ExportRequest, PreviewRequest
from app.services.ai_service import get_ai_suggestions
from app.services.document_parser import extract_text
from app.services.export_service import export_docx, export_pdf
from app.services.formatter import text_to_html, validate_format
from app.services.store import create_document, get_document, update_document

app = FastAPI(
    title="FormatFlow AI API",
    description="AI-powered academic paper formatting",
    version="2.0.0",
)

app.include_router(formatflow_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", "service": "FormatFlow AI"}


@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".docx", ".pdf", ".txt"}:
        raise HTTPException(status_code=400, detail="Supported: DOCX, PDF, TXT")

    temp_id = str(uuid.uuid4())
    save_path = UPLOAD_DIR / f"{temp_id}{suffix}"

    content = await file.read()
    save_path.write_bytes(content)

    try:
        text = extract_text(save_path)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not parse file: {e}") from e

    document_id = create_document(save_path, text, file.filename)
    preview_html = text_to_html(text, "IEEE")

    return {
        "document_id": document_id,
        "filename": file.filename,
        "preview": preview_html,
        "word_count": len(text.split()),
        "user": user.get("email"),
    }


@app.post("/convert")
async def convert_document(
    body: ConvertRequest,
    user: dict = Depends(get_current_user),
):
    doc = get_document(body.document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        fmt = validate_format(body.format)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    text = doc["text"]
    preview_html = text_to_html(text, fmt)
    export_docx(text, body.document_id, fmt)

    update_document(
        body.document_id,
        format=fmt,
        preview_html=preview_html,
    )

    return {
        "document_id": body.document_id,
        "format": fmt,
        "preview_html": preview_html,
        "preview": preview_html,
        "message": f"Document converted to {fmt}",
        "user": user.get("email"),
    }


@app.post("/preview")
async def preview_document(
    body: PreviewRequest,
    user: dict = Depends(get_current_user),
):
    doc = get_document(body.document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    fmt = doc.get("format") or "IEEE"
    preview_html = doc.get("preview_html") or text_to_html(doc["text"], fmt)

    return {
        "document_id": body.document_id,
        "preview_html": preview_html,
        "preview": preview_html,
        "format": fmt,
    }


@app.post("/export")
async def export_document(
    body: ExportRequest,
    user: dict = Depends(get_current_user),
):
    doc = get_document(body.document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    fmt = doc.get("format") or "IEEE"
    text = doc["text"]
    export_type = body.export_format.lower()

    try:
        docx_path = export_docx(text, body.document_id, fmt)

        if export_type == "docx":
            return FileResponse(
                path=str(docx_path),
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                filename=f"scholarai_{fmt}.docx",
            )

        try:
            pdf_path = export_pdf(docx_path, body.document_id, fmt)
            return FileResponse(
                path=str(pdf_path),
                media_type="application/pdf",
                filename=f"scholarai_{fmt}.pdf",
            )
        except RuntimeError as e:
            raise HTTPException(status_code=503, detail=str(e)) from e

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/ai-suggestions")
async def ai_suggestions(
    body: AiSuggestionsRequest,
    user: dict = Depends(get_current_user),
):
    doc = get_document(body.document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        fmt = validate_format(body.format)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    suggestions = get_ai_suggestions(doc["text"], fmt)

    return {
        "document_id": body.document_id,
        "format": fmt,
        "suggestions": suggestions,
    }
