from __future__ import annotations

import base64
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from app.config import IMAGE_DIR, PDF_DIR, TEX_DIR
from app.models.document_schema import SemanticDocument


COMMON_PACKAGES = [
    r"\usepackage{amsmath}",
    r"\usepackage{amssymb}",
    r"\usepackage{graphicx}",
    r"\usepackage{booktabs}",
    r"\usepackage{multirow}",
    r"\usepackage{array}",
    r"\usepackage{url}",
    r"\usepackage{float}",
    r"\usepackage{hyperref}",
]


def ensure_latex_bundle(document_id: str) -> Path:
    bundle_dir = TEX_DIR / document_id
    bundle_dir.mkdir(parents=True, exist_ok=True)
    (bundle_dir / "images").mkdir(parents=True, exist_ok=True)
    return bundle_dir


def semantic_to_latex(doc: SemanticDocument) -> str:
    title = _latex_escape(doc.title or "Untitled Paper")
    body_parts: list[str] = []
    front_matter = _front_matter_latex(title, doc.authors)
    body_parts.extend(_structured_body_latex(doc))

    return "\n".join([
        r"\documentclass[conference]{IEEEtran}",
        *COMMON_PACKAGES,
        *front_matter,
        r"\begin{document}",
        r"\maketitle",
        *body_parts,
        r"\end{document}",
    ])


def write_latex_bundle(document_id: str, doc: SemanticDocument) -> Path:
    bundle_dir = ensure_latex_bundle(document_id)
    tex_path = bundle_dir / "paper.tex"
    tex_path.write_text(semantic_to_latex(doc), encoding="utf-8")
    _write_images(bundle_dir, doc)
    return tex_path


def compile_latex(tex_path: Path) -> tuple[Path | None, list[dict[str, str]]]:
    pdf_path = tex_path.with_suffix(".pdf")
    if not _latex_engine_available():
        return None, [
            {
                "line": "0",
                "severity": "error",
                "message": "No LaTeX engine found. Install pdflatex or xelatex to enable live compilation.",
            }
        ]

    command = _latex_engine_command()
    if not command:
        return None, [
            {
                "line": "0",
                "severity": "error",
                "message": "No LaTeX engine found. Install pdflatex or xelatex to enable live compilation.",
            }
        ]

    compile_errors: list[dict[str, str]] = []
    for _ in range(2):
        proc = subprocess.run(
            [*command, tex_path.name],
            cwd=tex_path.parent,
            capture_output=True,
            text=True,
            timeout=120,
        )
        compile_errors = _parse_latex_errors(proc.stdout + "\n" + proc.stderr)
        if proc.returncode != 0:
            return None, compile_errors or [
                {
                    "line": "0",
                    "severity": "error",
                    "message": "LaTeX compilation failed.",
                }
            ]

    if pdf_path.exists():
        final_pdf = PDF_DIR / tex_path.parent.name / pdf_path.name
        final_pdf.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pdf_path, final_pdf)
        return final_pdf, compile_errors

    return None, compile_errors


def latex_to_semantic(tex: str, base_doc: SemanticDocument) -> SemanticDocument:
    title = _extract_command(tex, "title") or base_doc.title
    authors = _extract_command(tex, "author") or ", ".join(author.name for author in base_doc.authors)
    abstract = _extract_environment(tex, "abstract") or base_doc.abstract
    keywords = _extract_keywords(tex) or base_doc.keywords
    sections = _extract_sections(tex)
    references = _extract_references(tex)

    from app.models.document_schema import Author, Reference, Section

    return SemanticDocument(
        id=base_doc.id,
        filename=base_doc.filename,
        format_target=base_doc.format_target,
        title=title,
        authors=[Author(name=name.strip()) for name in re.split(r"\\and|,", authors) if name.strip()],
        abstract=abstract,
        keywords=keywords,
        sections=[Section(id=f"sec-{idx}", type="heading", level=1, title=section, source_index=idx) for idx, section in enumerate(sections)],
        figures=base_doc.figures,
        tables=base_doc.tables,
        references=[Reference(id=f"ref-{idx+1}", text=ref, order=idx+1) for idx, ref in enumerate(references)],
        elements=base_doc.elements,
        metadata={**base_doc.metadata, "latex_synced": True},
    )


def _front_matter_latex(title: str, authors: list[Any]) -> list[str]:
    parts = [rf"\title{{{title}}}"]
    if authors:
        parts.append(_authors_latex(authors))
    else:
        parts.append(r"\author{Author Name}")
    return parts


def _authors_latex(authors: list[Any]) -> str:
    blocks: list[str] = []
    for author in authors:
        name = _latex_escape(getattr(author, "name", "Author Name") or "Author Name")
        affiliation = _latex_escape(getattr(author, "affiliation", "") or "").strip()
        email = _latex_escape(getattr(author, "email", "") or "").strip()
        detail_lines = [line for line in [affiliation, email] if line]
        if detail_lines:
            detail = r"\\".join(detail_lines)
            blocks.append(rf"\IEEEauthorblockN{{{name}}}\IEEEauthorblockA{{{detail}}}")
        else:
            blocks.append(rf"\IEEEauthorblockN{{{name}}}")
    authors_block = r"\and".join(blocks) if blocks else r"\IEEEauthorblockN{Author Name}"
    return "\n".join([r"\author{", authors_block, r"}"])


def _structured_body_latex(doc: SemanticDocument) -> list[str]:
    parts: list[str] = []
    if doc.abstract:
        parts.extend([
            r"\begin{abstract}",
            _latex_text(doc.abstract),
            r"\end{abstract}",
        ])
    if doc.keywords:
        keywords = ", ".join(_latex_escape(keyword) for keyword in doc.keywords)
        parts.append(rf"\begin{{IEEEkeywords}} {keywords} \end{{IEEEkeywords}}")

    body_blocks: list[tuple[int, str, Any]] = []
    if doc.sections:
        for section in doc.sections:
            body_blocks.append((section.source_index, "section", section))
    if doc.figures:
        for figure in doc.figures:
            body_blocks.append((figure.source_index, "figure", figure))
    if doc.tables:
        for table in doc.tables:
            body_blocks.append((table.source_index, "table", table))

    for _, kind, block in sorted(body_blocks, key=lambda item: item[0]):
        if kind == "section":
            parts.extend(_section_to_latex(block))
        elif kind == "figure":
            parts.extend(_figure_to_latex(block))
        elif kind == "table":
            parts.extend(_table_to_latex_block(block))

    if doc.references:
        parts.append(r"\section*{References}")
        for ref in sorted(doc.references, key=lambda item: item.order):
            parts.append(rf"\noindent [{ref.order}] {_latex_text(ref.text)}\\")

    if not parts and doc.elements:
        parts.extend(_elements_to_latex(doc, doc.elements))
    return parts


def _section_to_latex(section: Any) -> list[str]:
    parts: list[str] = []
    title = _latex_escape(getattr(section, "title", "") or getattr(section, "content", ""))
    content = _latex_text(getattr(section, "content", ""))
    if title:
        level = max(1, min(int(getattr(section, "level", 1) or 1), 3))
        prefix = "sub" * (level - 1)
        parts.append(f"\\{prefix}section{{{title}}}")
    if content and content != title:
        parts.append(content)
    children = getattr(section, "children", []) or []
    for child in children:
        parts.extend(_section_to_latex(child))
    return parts


def _figure_to_latex(figure: Any) -> list[str]:
    caption = getattr(figure, "caption", "") or getattr(figure, "alt", "Figure")
    image_b64 = getattr(figure, "image_b64", None)
    content_type = getattr(figure, "content_type", None)
    width_pct = getattr(figure, "width_pct", 100.0) or 100.0
    if not image_b64:
        return [r"\begin{figure}[t]", r"\centering", r"\fbox{Missing image}", rf"\caption{{{_latex_escape(caption)}}}", r"\end{figure}"]
    ext = (content_type or "image/png").split("/")[-1]
    image_name = _figure_filename(figure)
    width = "0.95\\linewidth" if width_pct >= 90 else f"{max(0.5, min(width_pct / 100.0, 0.95)):.2f}\\linewidth"
    return [
        r"\begin{figure}[t]",
        r"\centering",
        rf"\includegraphics[width={width}]{{images/{image_name}.{ext}}}",
        rf"\caption{{{_latex_escape(caption)}}}",
        r"\end{figure}",
    ]


def _table_to_latex_block(table: Any) -> list[str]:
    rows = getattr(table, "rows", []) or []
    caption = getattr(table, "caption", "") or getattr(table, "id", "Table")
    if not rows:
        return []
    col_count = max(len(row) for row in rows)
    cols = "|" + "|".join(["p{0.3\\linewidth}"] * col_count) + "|"
    lines = [r"\begin{table}[t]", r"\centering", rf"\caption{{{_latex_escape(caption)}}}", rf"\begin{{tabular}}{{{cols}}}", r"\hline"]
    for row in rows:
        cells = [_latex_text(cell) for cell in row]
        cells.extend([""] * (col_count - len(cells)))
        lines.append(" & ".join(cells) + r" \\")
        lines.append(r"\hline")
    lines.extend([r"\end{tabular}", r"\end{table}"])
    return lines


def _fallback_semantic_latex(doc: SemanticDocument) -> list[str]:
    return _structured_body_latex(doc)


def _elements_to_latex(doc: SemanticDocument, elements: list[Any]) -> list[str]:
    parts: list[str] = []
    for element in elements:
        kind = getattr(element, "type", "")
        content = _latex_text(getattr(element, "content", ""))
        if kind == "title":
            continue
        if kind == "author":
            continue
        if kind == "keyword":
            continue
        if kind == "heading":
            level = max(1, min(int(getattr(element, "level", 1) or 1), 3))
            section_prefix = "sub" * (level - 1)
            parts.append(f"\\{section_prefix}section{{{content}}}")
            continue
        if kind == "paragraph":
            parts.append(content)
            continue
        if kind in {"figure", "image"}:
            parts.extend(_element_figure_latex(element))
            continue
        if kind == "table":
            rows = getattr(element, "rows", [])
            caption = getattr(element, "caption", "") or content or "Table"
            parts.extend(_table_latex(rows, caption))
            continue
        if kind == "references":
            parts.append(r"\section*{References}")
            continue
        if kind == "reference":
            parts.append(rf"\noindent {content}\\")
    return parts


def _figure_latex(caption: str, image_b64: str | None, content_type: str | None) -> list[str]:
    if not image_b64:
        return [r"\begin{figure}[t]", r"\centering", r"\fbox{Missing image}", rf"\caption{{{_latex_escape(caption)}}}", r"\end{figure}"]
    ext = (content_type or "image/png").split("/")[-1]
    return [
        r"\begin{figure}[t]",
        r"\centering",
        rf"\includegraphics[width=\linewidth]{{images/{captionify(caption)}.{ext}}}",
        rf"\caption{{{_latex_escape(caption)}}}",
        r"\end{figure}",
    ]


def _element_figure_latex(element: Any) -> list[str]:
    caption = getattr(element, "caption", "") or getattr(element, "content", "Figure")
    src = getattr(element, "src", None) or ""
    if src.startswith("data:") and "," in src:
        content_type = src.split(";")[0][5:]
        image_name = captionify(caption)
        ext = (content_type or "image/png").split("/")[-1]
        return [
            r"\begin{figure}[t]",
            r"\centering",
            rf"\includegraphics[width=\linewidth]{{images/{image_name}.{ext}}}",
            rf"\caption{{{_latex_escape(caption)}}}",
            r"\end{figure}",
        ]
    return [r"\begin{figure}[t]", r"\centering", r"\fbox{Image}", rf"\caption{{{_latex_escape(caption)}}}", r"\end{figure}"]


def _table_latex(rows: list[list[str]], caption: str) -> list[str]:
    if not rows:
        return []
    col_count = max(len(row) for row in rows)
    cols = "|" + "|".join(["p{0.3\\linewidth}"] * col_count) + "|"
    lines = [r"\begin{table}[t]", r"\centering", rf"\caption{{{_latex_escape(caption)}}}", rf"\begin{{tabular}}{{{cols}}}", r"\hline"]
    for row in rows:
        cells = [_latex_text(cell) for cell in row]
        cells.extend([""] * (col_count - len(cells)))
        lines.append(" & ".join(cells) + r" \\")
        lines.append(r"\hline")
    lines.extend([r"\end{tabular}", r"\end{table}"])
    return lines


def _write_images(bundle_dir: Path, doc: SemanticDocument) -> None:
    images_dir = bundle_dir / "images"
    for index, figure in enumerate(doc.figures, start=1):
        if not figure.image_b64:
            continue
        ext = (figure.content_type or "image/png").split("/")[-1]
        image_path = images_dir / f"{_figure_filename(figure, index)}.{ext}"
        image_path.write_bytes(base64.b64decode(figure.image_b64))


def _figure_filename(figure: Any, fallback_index: int | None = None) -> str:
    base = getattr(figure, "id", "") or getattr(figure, "caption", "") or f"figure-{fallback_index or 0}"
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", str(base)).strip("-")
    return slug or f"figure-{fallback_index or 0}"


def _latex_escape(text: str) -> str:
    return (
        text.replace("\\", r"\textbackslash{}")
        .replace("&", r"\&")
        .replace("%", r"\%")
        .replace("$", r"\$")
        .replace("#", r"\#")
        .replace("_", r"\_")
        .replace("{", r"\{")
        .replace("}", r"\}")
        .replace("~", r"\textasciitilde{}")
        .replace("^", r"\textasciicircum{}")
    )


def _latex_text(text: str) -> str:
    return _latex_escape(re.sub(r"\s+", " ", text or "").strip())


def captionify(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()[:48] or "figure"


def _latex_engine_available() -> bool:
    return bool(shutil.which("xelatex") or shutil.which("pdflatex"))


def _latex_engine_command() -> list[str] | None:
    if shutil.which("xelatex"):
        return ["xelatex", "-interaction=nonstopmode", "-halt-on-error"]
    if shutil.which("pdflatex"):
        return ["pdflatex", "-interaction=nonstopmode", "-halt-on-error"]
    return None


def _parse_latex_errors(output: str) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    for match in re.finditer(r"! (.+?)\n(?:l\.(\d+))?", output, flags=re.S):
        message = re.sub(r"\s+", " ", match.group(1)).strip()
        line = match.group(2) or "0"
        errors.append({"line": line, "severity": "error", "message": message})
    for match in re.finditer(r"LaTeX Warning: (.+?) on input line (\d+)", output):
        errors.append({"line": match.group(2), "severity": "warning", "message": match.group(1).strip()})
    return errors


def _extract_command(tex: str, command: str) -> str:
    match = re.search(rf"\\{command}\{{(.*?)\}}", tex, flags=re.S)
    return re.sub(r"\s+", " ", match.group(1)).strip() if match else ""


def _extract_environment(tex: str, environment: str) -> str:
    match = re.search(rf"\\begin\{{{environment}\}}(.*?)\\end\{{{environment}\}}", tex, flags=re.S)
    return re.sub(r"\s+", " ", match.group(1)).strip() if match else ""


def _extract_keywords(tex: str) -> list[str]:
    keywords = _extract_command(tex, "IEEEkeywords")
    if not keywords:
        return []
    return [item.strip() for item in re.split(r",|;", keywords) if item.strip()]


def _extract_sections(tex: str) -> list[str]:
    return [match.strip() for match in re.findall(r"\\(?:sub)*section\{(.*?)\}", tex, flags=re.S)]


def _extract_references(tex: str) -> list[str]:
    if "References" not in tex:
        return []
    refs = re.findall(r"\\noindent\s*(.+?)\\\\", tex, flags=re.S)
    return [re.sub(r"\s+", " ", ref).strip() for ref in refs if ref.strip()]