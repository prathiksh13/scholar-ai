"""Shared page layout engine for preview and PDF export."""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass, field
from html import escape
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.platypus import Paragraph, Table, TableStyle

from app.models.document_schema import DocumentElement, SemanticDocument
from app.rules.ieee import get_ieee_rules


@dataclass
class LayoutBlock:
    kind: str
    page: int
    x: float
    y: float
    width: float
    height: float
    content: str = ""
    html: str = ""
    align: str = "left"
    level: int = 1
    image_b64: str | None = None
    content_type: str | None = None
    rows: list[list[str]] = field(default_factory=list)
    caption: str = ""
    order: int = 0
    full_width: bool = False


@dataclass
class LayoutPage:
    number: int
    blocks: list[LayoutBlock] = field(default_factory=list)


@dataclass
class LayoutDocument:
    page_width: float
    page_height: float
    margin: float
    column_gap: float
    column_width: float
    pages: list[LayoutPage] = field(default_factory=list)

    def to_html(self) -> str:
        parts = [
            '<div class="formatflow-layout">',
        ]
        for page in self.pages:
            parts.append(
                f'<section class="formatflow-page" data-page-number="{page.number}" '
                f'style="width:{self.page_width}pt;height:{self.page_height}pt;">'
            )
            parts.append('<div class="formatflow-page-surface">')
            parts.append('<div class="formatflow-page-ruler"></div>')
            for block in page.blocks:
                parts.append(_block_to_html(block))
            parts.append('</div></section>')
        parts.append('</div>')
        return "".join(parts)


@dataclass
class PageCursor:
    page: int = 1
    column: int = 0
    x: float = 0.0
    y: float = 0.0
    remaining_height: float = 0.0
    body_top: float = 0.0
    body_bottom: float = 0.0


def layout_document(doc: SemanticDocument) -> LayoutDocument:
    rules = get_ieee_rules()
    page_width, page_height = A4
    margin = rules.margins_inch * inch
    column_gap = rules.column_gap_inch * inch
    content_width = page_width - margin * 2
    column_width = (content_width - column_gap) / 2
    body_bottom = page_height - margin

    layout = LayoutDocument(
        page_width=page_width,
        page_height=page_height,
        margin=margin,
        column_gap=column_gap,
        column_width=column_width,
    )

    cursor = PageCursor(page=1, column=0, x=margin, y=margin, body_top=margin, body_bottom=body_bottom)
    _sync_cursor(layout, cursor)
    layout.pages.append(LayoutPage(number=1))

    front_items = _front_matter_items(doc)
    body_items = _body_items(doc)

    for item in front_items:
        _layout_front_block(item, layout, cursor, content_width, body_bottom)

    cursor.body_top = cursor.y + 10
    cursor.y = cursor.body_top
    cursor.column = 0
    _sync_cursor(layout, cursor)
    if cursor.remaining_height <= 0:
        _new_page(layout, cursor)

    for item in body_items:
        if item.type == "page_break":
            _new_page(layout, cursor)
            continue

        # Decide whether the block should span both columns (full width)
        is_full = False
        if item.type in {"figure", "image", "table"}:
            pct = float(item.width_pct or 100.0)
            if pct >= 90.0:
                width = content_width
                is_full = True
            else:
                width = column_width
        else:
            width = column_width

        _layout_body_block(item, layout, cursor, width, is_full, body_bottom)

    return layout


def render_layout_to_pdf(layout: LayoutDocument, out_path: str, title: str = "") -> None:
    pdf = pdf_canvas.Canvas(out_path, pagesize=(layout.page_width, layout.page_height))
    styles = _styles()

    for page in layout.pages:
        _draw_page_background(pdf, layout)
        for block in page.blocks:
            _draw_pdf_block(pdf, block, styles, layout)
        pdf.showPage()

    pdf.save()


def _front_matter_items(doc: SemanticDocument) -> list[DocumentElement]:
    items: list[DocumentElement] = []
    if doc.title:
        items.append(DocumentElement(type="title", content=doc.title, order=0))
    if doc.authors:
        author_lines: list[str] = []
        for author in doc.authors:
            details = [author.name]
            if author.affiliation:
                details.append(author.affiliation)
            if author.email:
                details.append(author.email)
            author_lines.append("\n".join(details))
        items.append(DocumentElement(type="author", content="\n\n".join(author_lines), order=1))
    if doc.keywords:
        items.append(DocumentElement(type="keyword", content=", ".join(doc.keywords), order=2))
    if doc.abstract:
        items.append(DocumentElement(type="heading", content="Abstract", order=3, level=1))
        items.append(DocumentElement(type="paragraph", content=doc.abstract, order=4))
    return items


def _body_items(doc: SemanticDocument) -> list[DocumentElement]:
    structured_items: list[DocumentElement] = []
    for section in sorted(doc.sections, key=lambda item: item.source_index):
        if section.title:
            structured_items.append(DocumentElement(type="heading", content=section.title, order=section.source_index, level=section.level))
        if section.content:
            structured_items.append(DocumentElement(type="paragraph", content=section.content, order=section.source_index))
    for figure in sorted(doc.figures, key=lambda item: item.source_index):
        structured_items.append(
            DocumentElement(
                type="figure",
                content=figure.caption,
                order=figure.source_index,
                caption=figure.caption,
                src=_figure_src(figure),
                width_pct=getattr(figure, "width_pct", None),
            )
        )
    for table in sorted(doc.tables, key=lambda item: item.source_index):
        structured_items.append(
            DocumentElement(
                type="table",
                content=table.caption,
                order=table.source_index,
                caption=table.caption,
                html=table.html,
                rows=getattr(table, "rows", None) or [],
                width_pct=getattr(table, "width_pct", None),
            )
        )
    if doc.references:
        structured_items.append(DocumentElement(type="references", content="References", order=len(structured_items)))
        for reference in sorted(doc.references, key=lambda item: item.order):
            structured_items.append(DocumentElement(type="reference", content=reference.text, order=reference.order))
    if structured_items:
        return structured_items

    if doc.elements:
        items: list[DocumentElement] = []
        seen_abstract_heading = False
        skipped_abstract_paragraph = False
        for element in doc.elements:
            if element.type in {"title", "author", "keyword"}:
                continue
            if element.type == "heading" and _is_abstract_heading(element.content):
                seen_abstract_heading = True
                continue
            if seen_abstract_heading and not skipped_abstract_paragraph and element.type == "paragraph":
                skipped_abstract_paragraph = True
                continue
            items.append(element)
        return items

    return []


def _layout_front_block(
    item: DocumentElement,
    layout: LayoutDocument,
    cursor: PageCursor,
    width: float,
    body_bottom: float,
) -> LayoutBlock | None:
    styles = _styles()
    if item.type == "title":
        return _place_text(item, layout, cursor, width, body_bottom, styles["title"], align="center", kind="title", spacing_after=6)
    if item.type == "author":
        author_html = _author_html(item.content)
        return _place_text(item, layout, cursor, width, body_bottom, styles["authors"], align="center", kind="author", html_override=author_html, spacing_after=6)
    if item.type == "keyword":
        text = f"<b>Keywords:</b> {escape(item.content)}"
        return _place_text(item, layout, cursor, width, body_bottom, styles["body"], align="left", kind="keyword", html_override=text, spacing_after=4)
    if item.type == "heading" and _is_abstract_heading(item.content):
        return _place_text(item, layout, cursor, width, body_bottom, styles["heading2"], align="left", kind="heading", spacing_after=4)
    if item.type == "paragraph":
        return _place_text(item, layout, cursor, width, body_bottom, styles["body"], align="justify", kind="paragraph", spacing_after=8)
    return None


def _layout_body_block(
    item: DocumentElement,
    layout: LayoutDocument,
    cursor: PageCursor,
    width: float,
    full_width: bool,
    body_bottom: float,
) -> LayoutBlock | None:
    styles = _styles()
    block_kind = item.type
    spacing_after = 4
    if block_kind == "heading":
        if _is_reference_heading(item.content):
            return _place_text(item, layout, cursor, width, body_bottom, styles["heading2"], align="left", kind="references", spacing_after=6)
        return _place_text(item, layout, cursor, width, body_bottom, styles["heading3"], align="left", kind="heading", spacing_after=4)
    if block_kind == "paragraph":
        return _place_text(item, layout, cursor, width, body_bottom, styles["body"], align="justify", kind="paragraph", spacing_after=4)
    if block_kind in {"figure", "image"}:
        return _place_figure(item, layout, cursor, width, full_width, body_bottom)
    if block_kind == "table":
        return _place_table(item, layout, cursor, width, full_width, body_bottom)
    if block_kind == "reference":
        text = f"[{item.order}] {item.content}"
        return _place_text(item, layout, cursor, width, body_bottom, styles["reference"], align="left", kind="reference", html_override=text, spacing_after=3)
    if block_kind == "references":
        return _place_text(item, layout, cursor, width, body_bottom, styles["heading2"], align="left", kind="references", spacing_after=4)
    return None


def _place_text(
    item: DocumentElement,
    layout: LayoutDocument,
    cursor: PageCursor,
    width: float,
    body_bottom: float,
    style: ParagraphStyle,
    *,
    align: str,
    kind: str,
    html_override: str | None = None,
    spacing_after: float = 4,
) -> LayoutBlock:
    block_width = width
    paragraph_html = html_override or _text_to_html(item.content)
    paragraph = Paragraph(paragraph_html, style)
    _, height = paragraph.wrap(block_width, 10000)
    _reserve_space(layout, cursor, height + spacing_after, body_bottom)
    x = cursor.x if cursor.column == 0 and block_width == layout.column_width else _column_x(layout, cursor, block_width)
    y = cursor.y
    block = LayoutBlock(
        kind=kind,
        page=cursor.page,
        x=x,
        y=y,
        width=block_width,
        height=height,
        content=item.content,
        html=paragraph_html,
        align=align,
        level=item.level,
        order=item.order,
    )
    _append_block(layout, cursor, block, spacing_after)
    return block


def _place_figure(item: DocumentElement, layout: LayoutDocument, cursor: PageCursor, width: float, full_width: bool, body_bottom: float) -> LayoutBlock:
    caption = item.caption or item.content or "Figure"
    figure_width_pct = item.width_pct or 100.0
    image_width = max(120.0, width * min(figure_width_pct / 100.0, 1.0))
    image_height = 0.0
    if item.src and item.src.startswith("data:") and "," in item.src:
        try:
            header, encoded = item.src.split(",", 1)
            image_bytes = base64.b64decode(encoded)
            reader = ImageReader(BytesIO(image_bytes))
            source_w, source_h = reader.getSize()
            image_height = image_width * (source_h / max(source_w, 1))
        except Exception:
            image_height = width * 0.65
    else:
        image_height = width * 0.65
    caption_style = _styles()["caption"]
    caption_html = _text_to_html(caption)
    caption_height = Paragraph(caption_html, caption_style).wrap(width, 10000)[1]
    usable_height = _usable_body_height(cursor)
    max_image_height = max(usable_height - caption_height - 12, 72.0)
    image_height = min(image_height, max_image_height)
    total_height = image_height + 8 + caption_height
    # If this is intended to be full-width ensure we place on column 0 at page margin
    if full_width and cursor.column == 1:
        _new_page(layout, cursor)
    _reserve_space(layout, cursor, total_height + 4, body_bottom)
    if full_width:
        x = layout.margin
    else:
        x = _column_x(layout, cursor, width)
    y = cursor.y
    html = _figure_html(item, width)
    block = LayoutBlock(
        kind="figure",
        page=cursor.page,
        x=x,
        y=y,
        width=width,
        height=total_height,
        content=caption,
        html=html,
        image_b64=_image_b64(item.src),
        content_type=_content_type(item.src),
        caption=caption,
        order=item.order,
    )
    _append_block(layout, cursor, block, 4)
    return block


def _place_table(item: DocumentElement, layout: LayoutDocument, cursor: PageCursor, width: float, full_width: bool, body_bottom: float) -> LayoutBlock:
    rows = _table_rows(item)
    caption_style = _styles()["caption"]
    caption_text = item.caption or item.content or "Table"
    table_width = max(140.0, width * min((item.width_pct or 100.0) / 100.0, 1.0))
    chunks = _split_table_rows(rows or [[caption_text]], table_width, caption_text, cursor)
    first_block: LayoutBlock | None = None

    for index, chunk_rows in enumerate(chunks):
        chunk_caption = caption_text if index == 0 else f"{caption_text} (cont.)"
        caption_html = _text_to_html(chunk_caption)
        caption_height = Paragraph(caption_html, caption_style).wrap(width, 10000)[1]
        table = _build_table(chunk_rows, table_width)
        _, table_height = table.wrap(table_width, 10000)
        total_height = caption_height + 6 + table_height
        # If this chunk should be full width, force placement at page margin and on a fresh page
        if full_width and cursor.column == 1:
            _new_page(layout, cursor)
        _reserve_space(layout, cursor, total_height + 4, body_bottom)
        if full_width:
            x = layout.margin
        else:
            x = _column_x(layout, cursor, table_width)
        y = cursor.y
        block = LayoutBlock(
            kind="table",
            page=cursor.page,
            x=x,
            y=y,
            width=table_width,
            height=total_height,
            content=item.content,
            html=_table_html(chunk_rows, chunk_caption),
            rows=chunk_rows,
            caption=chunk_caption,
            order=item.order,
        )
        _append_block(layout, cursor, block, 4)
        if first_block is None:
            first_block = block

    return first_block


def _append_block(layout: LayoutDocument, cursor: PageCursor, block: LayoutBlock, spacing_after: float) -> None:
    layout.pages[-1].blocks.append(block)
    cursor.y += block.height + spacing_after
    _sync_cursor(layout, cursor)


def _reserve_space(layout: LayoutDocument, cursor: PageCursor, height: float, body_bottom: float) -> None:
    cursor.body_bottom = body_bottom
    _sync_cursor(layout, cursor)
    usable_height = _usable_body_height(cursor)
    required_height = min(height, usable_height)
    while cursor.remaining_height < required_height:
        if cursor.column == 0:
            _advance_column(layout, cursor)
        else:
            _new_page(layout, cursor)
        if cursor.remaining_height >= required_height:
            break


def _advance_column(layout: LayoutDocument, cursor: PageCursor) -> None:
    cursor.column = 1
    cursor.y = cursor.body_top
    _sync_cursor(layout, cursor)


def _new_page(layout: LayoutDocument, cursor: PageCursor) -> None:
    cursor.page += 1
    cursor.column = 0
    cursor.y = layout.margin
    cursor.body_top = layout.margin
    cursor.body_bottom = layout.page_height - layout.margin
    layout.pages.append(LayoutPage(number=cursor.page))
    _sync_cursor(layout, cursor)


def _column_x(layout: LayoutDocument, cursor: PageCursor, width: float) -> float:
    if cursor.column == 0:
        return layout.margin
    return layout.margin + layout.column_width + layout.column_gap


def _sync_cursor(layout: LayoutDocument, cursor: PageCursor) -> None:
    cursor.x = _column_x(layout, cursor, layout.column_width)
    cursor.remaining_height = max(cursor.body_bottom - cursor.y, 0)


def _usable_body_height(cursor: PageCursor) -> float:
    return max(cursor.body_bottom - cursor.body_top, 0)


def _build_table(data: list[list[str]], table_width: float) -> Table:
    col_count = max(1, max(len(row) for row in data))
    col_widths = [table_width / col_count] * col_count
    normalized = [row + [""] * (col_count - len(row)) for row in data]
    table = Table(normalized, colWidths=col_widths, repeatRows=1 if len(normalized) > 1 else 0)
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Times-Roman"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("LEADING", (0, 0), (-1, -1), 11),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5eef8")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#93c5fd")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _split_table_rows(rows: list[list[str]], table_width: float, caption: str, cursor: PageCursor) -> list[list[list[str]]]:
    if not rows:
        return [[[caption]]]

    header = rows[:1] if len(rows) > 1 else []
    body_rows = rows[1:] if header else rows
    caption_height = Paragraph(_text_to_html(caption), _styles()["caption"]).wrap(table_width, 10000)[1]
    max_table_height = max(_usable_body_height(cursor) - caption_height - 10, 48.0)

    chunks: list[list[list[str]]] = []
    current = [list(row) for row in header] if header else []

    for row in body_rows:
        candidate = current + [list(row)]
        _, candidate_height = _build_table(candidate, table_width).wrap(table_width, 10000)
        if current and candidate_height > max_table_height and len(current) > len(header):
            chunks.append(current)
            current = [list(item) for item in header] if header else []
        current.append(list(row))

    if current:
        chunks.append(current)

    return chunks or [[[caption]]]


def _draw_page_background(pdf: pdf_canvas.Canvas, layout: LayoutDocument) -> None:
    pdf.setFillColor(colors.white)
    pdf.rect(0, 0, layout.page_width, layout.page_height, fill=1, stroke=0)


def _draw_pdf_block(pdf: pdf_canvas.Canvas, block: LayoutBlock, styles: dict[str, ParagraphStyle], layout: LayoutDocument) -> None:
    x = block.x
    y = layout.page_height - block.y - block.height
    if block.kind in {"title", "author", "keyword", "heading", "paragraph", "references", "reference"}:
        if block.kind == "title":
            style = styles["title"]
        elif block.kind == "author":
            style = styles["authors"]
        elif block.kind == "reference":
            style = styles["reference"]
        elif block.kind == "heading" and block.content.strip().lower() == "abstract":
            style = styles["heading2"]
        elif block.kind in {"heading", "references"}:
            style = styles["heading3"]
        else:
            style = styles["body"]
        paragraph = Paragraph(block.html or _text_to_html(block.content), style)
        paragraph.wrapOn(pdf, block.width, block.height)
        paragraph.drawOn(pdf, x, y)
        return
    if block.kind == "figure":
        _draw_pdf_figure(pdf, block, layout)
        return
    if block.kind == "table":
        _draw_pdf_table(pdf, block, layout)


def _draw_pdf_figure(pdf: pdf_canvas.Canvas, block: LayoutBlock, layout: LayoutDocument) -> None:
    top_y = layout.page_height - block.y
    caption_style = _styles()["caption"]
    caption_height = Paragraph(_text_to_html(block.caption or block.content), caption_style).wrap(block.width, 10000)[1]
    image_space = max(block.height - caption_height - 8, 1)
    image_y = top_y - block.height + caption_height + 8
    if block.image_b64:
        try:
            image_bytes = base64.b64decode(block.image_b64)
            reader = ImageReader(BytesIO(image_bytes))
            source_w, source_h = reader.getSize()
            draw_w = block.width
            draw_h = min(draw_w * (source_h / max(source_w, 1)), image_space)
            pdf.drawImage(reader, block.x, image_y, width=draw_w, height=draw_h, preserveAspectRatio=True, anchor='c')
        except Exception:
            pdf.setFont("Times-Roman", 9)
            pdf.drawString(block.x, image_y, "[figure]")
    else:
        pdf.setFont("Times-Roman", 9)
        pdf.drawString(block.x, image_y, "[figure]")
    caption = Paragraph(_text_to_html(block.caption or block.content), caption_style)
    caption.wrapOn(pdf, block.width, 10000)
    caption.drawOn(pdf, block.x, top_y - block.height)


def _draw_pdf_table(pdf: pdf_canvas.Canvas, block: LayoutBlock, layout: LayoutDocument) -> None:
    rows = block.rows or [[block.caption or block.content]]
    table = _build_table(rows, block.width)
    _, table_height = table.wrap(block.width, block.height)
    top_y = layout.page_height - block.y
    caption_style = _styles()["caption"]
    caption_height = Paragraph(_text_to_html(block.caption or block.content), caption_style).wrap(block.width, 10000)[1]
    table.drawOn(pdf, block.x, top_y - block.height + caption_height + 6)
    caption = Paragraph(_text_to_html(block.caption or block.content), caption_style)
    caption.wrapOn(pdf, block.width, 10000)
    caption.drawOn(pdf, block.x, top_y - block.height)


def _block_to_html(block: LayoutBlock) -> str:
    base_style = f"left:{block.x}pt;top:{block.y}pt;width:{block.width}pt;min-height:{block.height}pt;"
    if block.kind in {"title", "author", "keyword", "heading", "paragraph", "references", "reference"}:
        classes = f"layout-block layout-text layout-{block.kind}"
        return (
            f'<div class="{classes}" data-kind="{block.kind}" data-block-kind="{block.kind}" '
            f'data-block-order="{block.order}" style="{base_style}">{block.html or _text_to_html(block.content)}</div>'
        )
    if block.kind == "figure":
        inner = _figure_html_from_block(block)
        return (
            f'<div class="layout-block layout-figure" data-kind="figure" data-block-kind="figure" '
            f'data-block-order="{block.order}" style="{base_style}">{inner}</div>'
        )
    if block.kind == "table":
        inner = _table_html_from_block(block)
        return (
            f'<div class="layout-block layout-table" data-kind="table" data-block-kind="table" '
            f'data-block-order="{block.order}" style="{base_style}">{inner}</div>'
        )
    return f'<div class="layout-block" style="{base_style}">{escape(block.content)}</div>'


def _figure_html_from_block(block: LayoutBlock) -> str:
    if block.image_b64:
        image_src = f"data:image/png;base64,{block.image_b64}"
        img = f'<img src="{image_src}" alt="{escape(block.caption or block.content)}" />'
    else:
        img = '<div class="figure-placeholder">Figure</div>'
    caption = f'<figcaption>{escape(block.caption or block.content)}</figcaption>'
    return f'<figure>{img}{caption}</figure>'


def _table_html_from_block(block: LayoutBlock) -> str:
    rows = block.rows or [[block.caption or block.content]]
    table_rows = "".join(
        f'<tr>{"".join(f"<td>{escape(cell)}</td>" for cell in row)}</tr>'
        for row in rows
    )
    caption = f'<figcaption>{escape(block.caption or block.content)}</figcaption>'
    return f'<figure class="formatflow-table">{caption}<table><tbody>{table_rows}</tbody></table></figure>'


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("LayoutTitle", parent=base["Title"], fontName="Times-Bold", fontSize=16, leading=18, alignment=TA_CENTER, spaceAfter=6),
        "authors": ParagraphStyle("LayoutAuthors", parent=base["BodyText"], fontName="Times-Roman", fontSize=10, leading=12, alignment=TA_CENTER, spaceAfter=4),
        "heading2": ParagraphStyle("LayoutHeading2", parent=base["Heading2"], fontName="Times-Bold", fontSize=11, leading=13, alignment=TA_LEFT, spaceAfter=4),
        "heading3": ParagraphStyle("LayoutHeading3", parent=base["Heading3"], fontName="Times-Bold", fontSize=10.5, leading=12, alignment=TA_LEFT, spaceAfter=2),
        "body": ParagraphStyle("LayoutBody", parent=base["BodyText"], fontName="Times-Roman", fontSize=10, leading=12, alignment=TA_JUSTIFY, spaceAfter=3),
        "caption": ParagraphStyle("LayoutCaption", parent=base["BodyText"], fontName="Times-Italic", fontSize=8, leading=9, alignment=TA_CENTER, spaceAfter=2),
        "reference": ParagraphStyle("LayoutReference", parent=base["BodyText"], fontName="Times-Roman", fontSize=9, leading=11, alignment=TA_JUSTIFY, spaceAfter=2),
    }


def _text_to_html(value: str) -> str:
    return escape(re.sub(r"\s+", " ", value or "").strip()) or "&nbsp;"


def _author_html(value: str) -> str:
    authors = [chunk.strip() for chunk in re.split(r"\n\s*\n", value or "") if chunk.strip()]
    if not authors:
        return "&nbsp;"
    rendered: list[str] = []
    for author in authors:
        lines = [escape(line.strip()) for line in author.splitlines() if line.strip()]
        if lines:
            rendered.append("<br/>".join(lines))
    return "<br/><br/>".join(rendered) or "&nbsp;"


def _figure_src(element: DocumentElement | None) -> str | None:
    if not element:
        return None
    src = getattr(element, "src", None)
    if src:
        return src
    image_b64 = getattr(element, "image_b64", None)
    if image_b64:
        content_type = getattr(element, "content_type", None) or "image/png"
        return f"data:{content_type};base64,{image_b64}"
    return None


def _image_b64(src: str | None) -> str | None:
    if src and src.startswith("data:") and "," in src:
        return src.split(",", 1)[1]
    return None


def _content_type(src: str | None) -> str | None:
    if src and src.startswith("data:"):
        header = src.split(",", 1)[0]
        return header[5:].split(";", 1)[0]
    return None


def _table_rows(item: DocumentElement) -> list[list[str]]:
    if getattr(item, 'rows', None):
        return [list(row) for row in item.rows]
    if not item.html:
        return []
    rows: list[list[str]] = []
    try:
        for row in re.findall(r"<tr[^>]*>(.*?)</tr>", item.html, flags=re.I | re.S):
            cells = [re.sub(r"<[^>]+>", "", cell).strip() for cell in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, flags=re.I | re.S)]
            if cells:
                rows.append(cells)
    except Exception:
        return []
    return rows


def _figure_html(item: DocumentElement, width: float) -> str:
    if item.src and item.src.startswith("data:"):
        img = f'<img src="{escape(item.src)}" alt="{escape(item.caption or item.content)}" />'
    else:
        img = '<div class="figure-placeholder">Figure</div>'
    caption = f'<figcaption>{escape(item.caption or item.content)}</figcaption>'
    return f'<figure class="formatflow-figure" style="max-width:{width}pt;">{img}{caption}</figure>'


def _table_html(rows: list[list[str]], caption: str) -> str:
    table_rows = "".join(
        f'<tr>{"".join(f"<td>{escape(cell)}</td>" for cell in row)}</tr>'
        for row in rows
    )
    return f'<figure class="formatflow-table"><figcaption>{escape(caption)}</figcaption><table><tbody>{table_rows}</tbody></table></figure>'


def _is_abstract_heading(text: str) -> bool:
    return bool(re.match(r"^abstract\s*$", text, flags=re.I))


def _is_reference_heading(text: str) -> bool:
    return bool(re.match(r"^references?\s*$", text, flags=re.I))
