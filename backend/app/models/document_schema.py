"""Semantic document structure - canonical JSON representation."""

from html import escape
from typing import Any, Literal

from pydantic import BaseModel, Field


class Author(BaseModel):
    name: str
    affiliation: str | None = None
    email: str | None = None


class Figure(BaseModel):
    id: str
    caption: str = ""
    width_pct: float = 100.0
    position: Literal["inline", "float"] = "inline"
    alt: str = ""
    image_b64: str | None = None
    content_type: str | None = None
    source_index: int = 0


class TableBlock(BaseModel):
    id: str
    caption: str = ""
    rows: list[list[str]] = Field(default_factory=list)
    width_pct: float = 100.0
    source_index: int = 0
    html: str | None = None


class Reference(BaseModel):
    id: str
    text: str
    order: int = 0


class Section(BaseModel):
    id: str
    type: Literal["heading", "paragraph", "list"] = "paragraph"
    level: int = 1
    title: str | None = None
    content: str = ""
    children: list["Section"] = Field(default_factory=list)
    source_index: int = 0


class DocumentElement(BaseModel):
    type: Literal[
        "title",
        "author",
        "heading",
        "paragraph",
        "figure",
        "image",
        "table",
        "caption",
        "references",
        "reference",
        "keyword",
        "page_break",
    ]
    content: str = ""
    html: str | None = None
    src: str | None = None
    caption: str = ""
    rows: list[list[str]] = Field(default_factory=list)
    width: float | None = None
    height: float | None = None
    width_pct: float | None = None
    order: int = 0
    level: int = 1
    style: str | None = None


class SemanticDocument(BaseModel):
    id: str
    filename: str
    format_target: str = "IEEE"
    title: str = ""
    authors: list[Author] = Field(default_factory=list)
    abstract: str = ""
    keywords: list[str] = Field(default_factory=list)
    sections: list[Section] = Field(default_factory=list)
    figures: list[Figure] = Field(default_factory=list)
    tables: list[TableBlock] = Field(default_factory=list)
    references: list[Reference] = Field(default_factory=list)
    elements: list[DocumentElement] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_editor_html(self) -> str:
        """Render semantic doc as paginated HTML for preview."""
        try:
            from app.services.layout_engine import layout_document

            return layout_document(self).to_html()
        except Exception:
            columns = int(self.metadata.get("columns", 1) or 1)
            body_font = escape(str(self.metadata.get("body_font", "Times New Roman")))
            body_size = int(self.metadata.get("body_size_pt", 10) or 10)
            margin = self.metadata.get("margins_inch", 0.75)
            parts: list[str] = []
            parts.append(
                '<article '
                'class="formatflow-paper" '
                f'data-columns="{columns}" '
                f'style="--paper-columns:{columns}; --paper-font:{body_font}; '
                f'--paper-size:{body_size}pt; --paper-margin:{margin}in;">'
            )
            if self.elements:
                for element in self.elements:
                    parts.append(_element_html(element))
            else:
                if self.title:
                    parts.append(f'<h1 data-section="title">{escape(self.title)}</h1>')
                if self.authors:
                    authors_html = ", ".join(
                        f'<span data-author>{escape(a.name)}</span>' for a in self.authors
                    )
                    parts.append(f'<p class="authors" data-section="authors">{authors_html}</p>')
                if self.abstract:
                    parts.append('<h2 data-section="abstract">Abstract</h2>')
                    parts.append(f"<p>{escape(self.abstract)}</p>")
                if self.keywords:
                    kw = ", ".join(escape(keyword) for keyword in self.keywords)
                    parts.append(f'<p data-section="keywords"><strong>Keywords:</strong> {kw}</p>')

                ordered_blocks: list[tuple[int, str, object]] = []
                ordered_blocks.extend((sec.source_index, "section", sec) for sec in self.sections)
                ordered_blocks.extend((fig.source_index, "figure", fig) for fig in self.figures)
                ordered_blocks.extend((tbl.source_index, "table", tbl) for tbl in self.tables)
                for _, kind, block in sorted(ordered_blocks, key=lambda item: item[0]):
                    if kind == "section":
                        parts.extend(_section_html(block))
                        continue
                    if kind == "figure":
                        parts.append(_figure_html(block))
                        continue
                    parts.append(_table_html(block))

            if self.references and not self.elements:
                parts.append('<h2 data-section="references">References</h2>')
                parts.append("<ol>")
                for ref in sorted(self.references, key=lambda r: r.order):
                    parts.append(f'<li data-ref-id="{escape(ref.id)}">{escape(ref.text)}</li>')
                parts.append("</ol>")
            parts.append("</article>")
            return "\n".join(parts)


def _section_html(sec: Section) -> list[str]:
    out: list[str] = []
    if sec.type == "heading" or sec.title:
        tag = f"h{min(sec.level + 1, 6)}"
        text = sec.title or sec.content
        out.append(f'<{tag} data-section-id="{escape(sec.id)}">{escape(text)}</{tag}>')
    elif sec.content:
        out.append(f'<p data-section-id="{escape(sec.id)}">{escape(sec.content)}</p>')
    for child in sec.children:
        out.extend(_section_html(child))
    return out


def _figure_html(fig: Figure) -> str:
    image_html = (
        f'<img src="data:{escape(fig.content_type or "image/png")};base64,{fig.image_b64}" '
        f'alt="{escape(fig.alt or fig.caption or fig.id)}" '
        f'style="max-width:100%;height:auto;display:block;margin:0 auto;" />'
        if fig.image_b64
        else f'<div class="figure-placeholder">Figure {escape(fig.id)}</div>'
    )
    return (
        f'<figure data-figure-id="{escape(fig.id)}" class="formatflow-figure" '
        f'style="max-width:{fig.width_pct}%;">'
        f'{image_html}'
        f"<figcaption>{escape(fig.caption or fig.id)}</figcaption></figure>"
    )


def _table_html(tbl: TableBlock) -> str:
    table_rows = "".join(
        f'<tr>{"".join(f"<td>{escape(cell)}</td>" for cell in row)}</tr>'
        for row in tbl.rows
    )
    return (
        f'<figure data-table-id="{escape(tbl.id)}" class="formatflow-table" '
        f'style="max-width:{tbl.width_pct}%;">'
        f'<figcaption>{escape(tbl.caption or tbl.id)}</figcaption>'
        f'<table><tbody>{table_rows}</tbody></table></figure>'
    )


def _element_html(element: DocumentElement) -> str:
    if element.type in {"title", "author", "heading", "paragraph", "keyword"}:
        if element.type == "title":
            return f'<h1 data-section="title">{escape(element.content)}</h1>'
        if element.type == "author":
            return f'<p class="authors" data-section="authors">{escape(element.content)}</p>'
        if element.type == "heading":
            tag = f"h{min(element.level + 1, 6)}"
            return f'<{tag} data-element-order="{element.order}">{escape(element.content)}</{tag}>'
        if element.type == "keyword":
            return f'<p data-section="keywords"><strong>Keywords:</strong> {escape(element.content)}</p>'
        return f'<p data-element-order="{element.order}">{escape(element.content)}</p>'
    if element.type in {"figure", "image"}:
        return _element_figure_html(element)
    if element.type == "table":
        return element.html or f'<figure class="formatflow-table"><figcaption>{escape(element.caption)}</figcaption></figure>'
    if element.type == "caption":
        return f'<figcaption>{escape(element.content)}</figcaption>'
    if element.type == "references":
        return element.html or f'<h2 data-section="references">References</h2>'
    if element.type == "reference":
        return f'<p class="reference-item" data-reference-order="{element.order}">{escape(element.content)}</p>'
    if element.type == "page_break":
        return '<div class="page-break"></div>'
    return f'<p>{escape(element.content)}</p>'


def _element_figure_html(element: DocumentElement) -> str:
    image_html = element.html or (
        f'<img src="{escape(element.src or "")}" alt="{escape(element.caption or element.content)}" '
        'style="max-width:100%;height:auto;display:block;margin:0 auto;" />'
        if element.src
        else '<div class="figure-placeholder">Image</div>'
    )
    figcaption = element.caption or element.content
    return (
        f'<figure class="formatflow-figure" data-element-order="{element.order}">'
        f'{image_html}'
        f'<figcaption>{escape(figcaption)}</figcaption></figure>'
    )


Section.model_rebuild()
