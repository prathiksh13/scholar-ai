"""Document -> Semantic JSON pipeline with ordered block extraction."""

from __future__ import annotations

import base64
import mimetypes
import re
import uuid
from html import escape
from io import BytesIO
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph
from lxml import etree

from app.models.document_schema import (
    Author,
    DocumentElement,
    Figure,
    Reference,
    Section,
    SemanticDocument,
    TableBlock,
)

HEADING_PATTERNS = [
    (re.compile(r"^abstract\s*$", re.I), "abstract", 0),
    (re.compile(r"^introduction\s*$", re.I), "heading", 1),
    (re.compile(r"^references?\s*$", re.I), "references", 1),
    (re.compile(r"^\d+\.?\s+\w", re.I), "heading", 2),
    (re.compile(r"^(methodology|methods|results|discussion|conclusion)", re.I), "heading", 1),
]


def parse_docx_to_semantic(
    file_path: Path,
    document_id: str,
    filename: str,
) -> SemanticDocument:
    doc = Document(str(file_path))
    blocks = list(_iter_docx_blocks(doc))
    return _semantic_from_blocks(blocks, document_id, filename, source="docx")


def parse_pdf_to_semantic(
    file_path: Path,
    document_id: str,
    filename: str,
) -> SemanticDocument:
    blocks = _extract_pdf_blocks(file_path)
    return _semantic_from_blocks(blocks, document_id, filename, source="pdf")


def parse_document_to_semantic(
    file_path: Path,
    document_id: str,
    filename: str,
) -> SemanticDocument:
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return parse_pdf_to_semantic(file_path, document_id, filename)
    return parse_docx_to_semantic(file_path, document_id, filename)


def _semantic_from_blocks(
    blocks: list[DocumentElement],
    document_id: str,
    filename: str,
    source: str,
) -> SemanticDocument:
    title = ""
    authors: list[Author] = []
    abstract = ""
    keywords: list[str] = []
    sections: list[Section] = []
    figures: list[Figure] = []
    tables: list[TableBlock] = []
    references: list[Reference] = []
    elements: list[DocumentElement] = []
    pending_figure: Figure | None = None
    pending_figure_index: int | None = None
    in_abstract = False
    in_references = False

    for element in blocks:
        text = element.content.strip()

        if element.type == "page_break":
            elements.append(element)
            continue

        if element.type == "table":
            table = _table_from_element(element, len(tables) + 1)
            tables.append(table)
            elements.append(element)
            continue

        if element.type in {"figure", "image"}:
            figure = _figure_from_element(element, len(figures) + 1)
            figures.append(figure)
            pending_figure = figure
            pending_figure_index = len(elements)
            elements.append(
                DocumentElement(
                    type="figure",
                    content=figure.caption,
                    html=element.html,
                    src=element.src,
                    width=element.width,
                    height=element.height,
                    order=element.order,
                    caption=figure.caption,
                    style=element.style,
                )
            )
            continue

        if element.type == "caption" and pending_figure:
            pending_figure.caption = text or pending_figure.caption
            if pending_figure_index is not None and pending_figure_index < len(elements):
                elements[pending_figure_index].caption = pending_figure.caption
                if not elements[pending_figure_index].content:
                    elements[pending_figure_index].content = pending_figure.caption
            pending_figure = None
            pending_figure_index = None
            continue

        if pending_figure and element.type not in {"figure", "image", "caption"}:
            pending_figure = None
            pending_figure_index = None

        if element.type == "title" and not title:
            title = text
            elements.append(element)
            continue

        if element.type == "author":
            for name in re.split(r",| and ", text):
                name = name.strip()
                if name:
                    authors.append(Author(name=name))
            elements.append(element)
            continue

        if element.type == "keyword":
            keywords = [k.strip() for k in re.split(r"[,;]", text) if k.strip()]
            elements.append(element)
            continue

        if element.type == "references":
            in_references = True
            in_abstract = False
            elements.append(element)
            continue

        if element.type == "heading" and _is_abstract_heading(text):
            in_abstract = True
            in_references = False
            elements.append(element)
            continue

        if in_abstract and element.type == "paragraph":
            abstract += (" " if abstract else "") + text
            if len(abstract.split()) > 20 and _looks_like_new_section(text):
                in_abstract = False
            elements.append(element)
            continue

        if in_references and text:
            references.append(Reference(id=f"ref-{len(references) + 1}", text=text, order=len(references) + 1))
            elements.append(
                DocumentElement(
                    type="reference",
                    content=text,
                    order=element.order,
                    style=element.style,
                )
            )
            continue

        if element.type == "heading":
            sections.append(
                Section(
                    id=f"sec-{len(sections)}",
                    type="heading",
                    level=element.level,
                    title=text,
                    content="",
                    source_index=element.order,
                )
            )
            elements.append(element)
            continue

        if element.type == "paragraph" and text:
            if not title and len(text) > 0:
                title = text
                elements.append(
                    DocumentElement(
                        type="title",
                        content=text,
                        order=element.order,
                        style=element.style,
                    )
                )
                continue
            if not authors and _looks_like_authors(text) and title:
                authors.extend(Author(name=name.strip()) for name in re.split(r",| and ", text) if name.strip())
                elements.append(
                    DocumentElement(
                        type="author",
                        content=text,
                        order=element.order,
                        style=element.style,
                    )
                )
                continue
            sections.append(
                Section(
                    id=f"sec-{len(sections)}",
                    type="paragraph",
                    level=2,
                    content=text,
                    source_index=element.order,
                )
            )
            elements.append(element)
            continue

        elements.append(element)

    if not title and sections:
        title = sections[0].title or sections[0].content[:80]
        sections = sections[1:]

    # derive metadata and store the exact ordered source list for rendering/export
    semantic = SemanticDocument(
        id=document_id,
        filename=filename,
        title=title or "Untitled Paper",
        authors=authors or [Author(name="Author Name")],
        abstract=abstract.strip(),
        keywords=keywords,
        sections=sections,
        figures=figures,
        tables=tables,
        references=references,
        elements=elements or blocks,
        metadata={"source": source, "element_count": len(blocks)},
    )
    return semantic


def _looks_like_authors(text: str) -> bool:
    return len(text) < 200 and (
        "@" in text or "university" in text.lower() or "," in text
    )


def _is_figure_line(text: str) -> bool:
    return bool(re.match(r"^(figure|fig\.?)\s*\d+", text, re.I))


def _looks_like_caption(text: str) -> bool:
    return bool(re.match(r"^(figure|fig\.?)\s*\d+[:\.-]?", text, re.I)) or len(text) < 120 and text.lower().startswith(("source:", "caption:"))


def _extract_figure_from_paragraph(para: Paragraph, fig_number: int, source_index: int) -> Figure | None:
    try:
        for run in para.runs:
            drawings = run._element.xpath('.//a:blip')
            for drawing in drawings:
                rel_id = drawing.get(qn('r:embed'))
                if not rel_id:
                    continue
                rel = para.part.related_parts.get(rel_id)
                if not rel:
                    continue
                blob = getattr(rel, 'blob', None)
                if not blob:
                    continue
                content_type = getattr(rel, 'content_type', None)
                return Figure(
                    id=f"fig-{fig_number}",
                    caption=f"Figure {fig_number}",
                    width_pct=100.0,
                    position="inline",
                    alt=f"Figure {fig_number}",
                    image_b64=base64.b64encode(blob).decode('ascii'),
                    content_type=content_type,
                    source_index=source_index,
                )
    except Exception:
        return None
    return None


def _iter_docx_blocks(doc: Document):
    order = 0
    for child in doc.element.body.iterchildren():
        if child.tag.endswith("p"):
            paragraph = Paragraph(child, doc)
            element = _paragraph_to_element(paragraph, order)
            if element:
                yield element
                order += 1
        elif child.tag.endswith("tbl"):
            table = Table(child, doc)
            element = _table_to_element(table, order)
            yield element
            order += 1


def _paragraph_to_element(paragraph: Paragraph, order: int) -> DocumentElement | None:
    text = paragraph.text.strip()
    style_name = (paragraph.style.name or "").lower() if paragraph.style else ""
    image_html, image_src, image_width, image_height = _extract_images_from_paragraph(paragraph)

    if not text and not image_src:
        return None

    if image_src and not text:
        return DocumentElement(
            type="figure",
            content="",
            html=image_html,
            src=image_src,
            width=image_width,
            height=image_height,
            order=order,
            style=style_name,
        )

    if image_src and _looks_like_caption(text):
        return DocumentElement(
            type="figure",
            content=text,
            html=image_html,
            src=image_src,
            width=image_width,
            height=image_height,
            order=order,
            caption=text,
            style=style_name,
        )

    if _is_figure_line(text):
        return DocumentElement(type="caption", content=text, order=order, style=style_name)

    if order == 0:
        return DocumentElement(type="title", content=text, order=order, style=style_name)

    if _looks_like_authors(text):
        return DocumentElement(type="author", content=text, order=order, style=style_name)

    if _is_reference_heading(text, style_name):
        return DocumentElement(type="references", content=text, order=order, style=style_name)

    if _is_abstract_heading(text, style_name):
        return DocumentElement(type="heading", content=text, level=1, order=order, style=style_name)

    if _is_heading(text, style_name):
        return DocumentElement(type="heading", content=text, level=_heading_level(text, style_name), order=order, style=style_name)

    if re.match(r"^keywords?\s*:", text, re.I):
        return DocumentElement(type="keyword", content=re.sub(r"^keywords?\s*:\s*", "", text, flags=re.I), order=order, style=style_name)

    if image_src:
        return DocumentElement(
            type="paragraph",
            content=text,
            html=image_html,
            src=image_src,
            width=image_width,
            height=image_height,
            order=order,
            style=style_name,
        )

    return DocumentElement(type="paragraph", content=text, order=order, style=style_name)


def _table_to_element(table: Table, order: int) -> DocumentElement:
    html_table = _table_to_html(table)
    caption = f"Table {order + 1}"
    rows = _html_table_rows(html_table)
    return DocumentElement(type="table", content=caption, html=html_table, caption=caption, rows=rows, order=order)


def _extract_images_from_paragraph(paragraph: Paragraph):
    image_html = ""
    image_src = None
    width = None
    height = None
    try:
        root = etree.fromstring(paragraph._p.xml.encode("utf-8"))
        ns = root.nsmap.copy()
        ns.setdefault("wp", "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing")
        ns.setdefault("a", "http://schemas.openxmlformats.org/drawingml/2006/main")
        ns.setdefault("r", "http://schemas.openxmlformats.org/officeDocument/2006/relationships")
        ns.setdefault("pic", "http://schemas.openxmlformats.org/drawingml/2006/picture")

        for drawing in root.xpath('.//wp:inline | .//wp:anchor', namespaces=ns):
            rel_ids = drawing.xpath('.//a:blip/@r:embed', namespaces=ns)
            if not rel_ids:
                continue
            rel_id = rel_ids[0]
            rel = paragraph.part.related_parts.get(rel_id)
            if not rel:
                continue
            blob = getattr(rel, "blob", None)
            if not blob:
                continue
            content_type = getattr(rel, "content_type", None) or mimetypes.guess_type(getattr(rel, "partname", ""))[0] or "image/png"
            ext = "png"
            if content_type:
                ext = content_type.split("/")[-1]
            extents = drawing.xpath('./wp:extent', namespaces=ns)
            if extents:
                extent = extents[0]
                cx = int(extent.get("cx", "0") or 0)
                cy = int(extent.get("cy", "0") or 0)
                width = round(cx / 914400 * 96, 2) if cx else None
                height = round(cy / 914400 * 96, 2) if cy else None
            data_uri = f"data:{content_type};base64,{base64.b64encode(blob).decode('ascii')}"
            image_src = data_uri
            style = []
            if width:
                style.append(f"width:{min(width, 100)}%;")
            style.append("height:auto;display:block;margin:0 auto;")
            image_html = f'<img src="{data_uri}" alt="figure" style="{"".join(style)}" />'
            break
    except Exception:
        return "", None, None, None
    return image_html, image_src, width, height


def _table_to_html(table: Table) -> str:
    rows = []
    for row in table.rows:
        cells = []
        for cell in row.cells:
            text = escape(cell.text.strip())
            cells.append(f"<td>{text}</td>")
        rows.append(f"<tr>{''.join(cells)}</tr>")
    return f'<figure class="formatflow-table"><table><tbody>{"".join(rows)}</tbody></table></figure>'


def _is_abstract_heading(text: str, style_name: str = "") -> bool:
    return bool(re.match(r"^abstract\s*$", text, re.I)) or "abstract" in style_name


def _is_reference_heading(text: str, style_name: str = "") -> bool:
    return bool(re.match(r"^references?\s*$", text, re.I)) or "reference" in style_name


def _looks_like_new_section(text: str) -> bool:
    return bool(re.match(r"^(introduction|methodology|methods|results|discussion|conclusion|references?)", text, re.I))


def _figure_from_element(element: DocumentElement, figure_index: int) -> Figure:
    return Figure(
        id=f"fig-{figure_index}",
        caption=element.caption or element.content or f"Figure {figure_index}",
        width_pct=100.0,
        position="inline",
        alt=element.caption or element.content or f"Figure {figure_index}",
        image_b64=(element.src.split(",", 1)[1] if element.src and element.src.startswith("data:") and "," in element.src else None),
        content_type=(element.src.split(";", 1)[0].replace("data:", "") if element.src and element.src.startswith("data:") else None),
        source_index=element.order,
    )


def _table_from_element(element: DocumentElement, table_index: int) -> TableBlock:
    if element.html:
        rows = _html_table_rows(element.html)
    else:
        rows = []
    return TableBlock(
        id=f"tbl-{table_index}",
        caption=element.caption or element.content or f"Table {table_index}",
        rows=rows,
        width_pct=100.0,
        source_index=element.order,
        html=element.html,
    )


def _html_table_rows(html_table: str) -> list[list[str]]:
    rows: list[list[str]] = []
    try:
        root = etree.HTML(html_table)
        for tr in root.xpath(".//tr"):
            rows.append(["".join(td.xpath(".//text()")) for td in tr.xpath("./th|./td")])
    except Exception:
        return rows
    return rows


def _extract_pdf_blocks(file_path: Path) -> list[DocumentElement]:
    blocks: list[DocumentElement] = []
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(str(file_path))
        order = 0
        for page_index, page in enumerate(doc):
            blocks.append(DocumentElement(type="page_break", content=f"Page {page_index + 1}", order=order))
            order += 1
            for item in page.get_text("dict").get("blocks", []):
                bbox = item.get("bbox", [0, 0, 0, 0])
                if item.get("type") == 0:
                    text = "\n".join(
                        span.get("text", "")
                        for line in item.get("lines", [])
                        for span in line.get("spans", [])
                    ).strip()
                    if not text:
                        continue
                    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
                    for idx, line in enumerate(lines):
                        blocks.append(
                            DocumentElement(
                                type="heading" if _is_heading(line, "") and idx == 0 else "paragraph",
                                content=line,
                                order=order,
                                width=bbox[2] - bbox[0],
                                height=bbox[3] - bbox[1],
                            )
                        )
                        order += 1
                elif item.get("type") == 1:
                    img = item.get("image")
                    if img:
                        blocks.append(
                            DocumentElement(
                                type="figure",
                                content="",
                                src=f"data:image/png;base64,{base64.b64encode(img).decode('ascii')}" if isinstance(img, (bytes, bytearray)) else None,
                                order=order,
                                width=bbox[2] - bbox[0],
                                height=bbox[3] - bbox[1],
                            )
                        )
                        order += 1
        return blocks
    except Exception:
        return _extract_pdf_blocks_fallback(file_path)


def _extract_pdf_blocks_fallback(file_path: Path) -> list[DocumentElement]:
    blocks: list[DocumentElement] = []
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(file_path))
        order = 0
        for page_index, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if text.strip():
                for line in [ln.strip() for ln in text.splitlines() if ln.strip()]:
                    blocks.append(DocumentElement(type="paragraph", content=line, order=order))
                    order += 1
            blocks.append(DocumentElement(type="page_break", content=f"Page {page_index + 1}", order=order))
            order += 1
    except Exception:
        pass
    return blocks


def _is_heading(text: str, style_name: str) -> bool:
    if "heading" in style_name:
        return True
    for pat, kind, _ in HEADING_PATTERNS:
        if kind == "heading" and pat.match(text):
            return True
    return len(text) < 80 and text.isupper()


def _heading_level(text: str, style_name: str) -> int:
    m = re.search(r"heading\s*(\d)", style_name)
    if m:
        return int(m.group(1))
    if re.match(r"^\d+\.", text):
        return 2
    return 1


def new_document_id() -> str:
    return str(uuid.uuid4())
