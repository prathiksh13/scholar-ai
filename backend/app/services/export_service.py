import shutil
import subprocess
from pathlib import Path

from app.config import OUTPUT_DIR
from app.services.formatter import apply_format_to_docx, pandoc_convert


def export_docx(text: str, document_id: str, fmt: str) -> Path:
    return apply_format_to_docx(text, document_id, fmt)


def export_pdf(docx_path: Path, document_id: str, fmt: str) -> Path:
    pdf_path = OUTPUT_DIR / f"{document_id}_{fmt}.pdf"

    if pandoc_convert(docx_path, pdf_path, fmt):
        return pdf_path

    try:
        subprocess.run(
            [
                "pandoc",
                str(docx_path),
                "-o",
                str(pdf_path),
                "--pdf-engine=pdflatex",
            ],
            check=True,
            capture_output=True,
            timeout=90,
        )
        if pdf_path.exists():
            return pdf_path
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    # Fallback: copy docx path info — create minimal PDF via pandoc from text
    txt_path = OUTPUT_DIR / f"{document_id}_export.txt"
    from docx import Document

    doc = Document(str(docx_path))
    text = "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
    txt_path.write_text(text, encoding="utf-8")

    try:
        subprocess.run(
            ["pandoc", str(txt_path), "-o", str(pdf_path)],
            check=True,
            capture_output=True,
            timeout=60,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        # Last resort: return docx as downloadable (caller handles)
        shutil.copy(docx_path, pdf_path.with_suffix(".docx"))
        raise RuntimeError(
            "PDF export requires Pandoc. Install from https://pandoc.org/installing.html"
        ) from None

    return pdf_path
