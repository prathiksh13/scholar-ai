"""Apply format rules to semantic document → formatted semantic + actions."""

from copy import deepcopy

from app.models.document_schema import SemanticDocument
from app.rules.ieee import IEEE_RULES, FormatAction, get_ieee_rules
from app.services.compliance import run_compliance_check


def apply_format_rules(
    doc: SemanticDocument,
    format_name: str = "IEEE",
) -> tuple[SemanticDocument, list[FormatAction]]:
    formatted = deepcopy(doc)
    formatted.format_target = format_name.upper()
    actions: list[FormatAction] = []

    if format_name.upper() != "IEEE":
        actions.append(
            FormatAction(
                id="unsupported",
                message=f"{format_name} not available in MVP — using IEEE rules",
                category="warning",
                explanation="MVP supports IEEE only.",
            )
        )

    rules = get_ieee_rules()

    if formatted.abstract:
        words = len(formatted.abstract.split())
        if words > rules.abstract_max_words:
            formatted.abstract = " ".join(formatted.abstract.split()[: rules.abstract_max_words])
            actions.append(
                FormatAction(
                    id="abstract-trim",
                    message=f"Trimmed abstract to {rules.abstract_max_words} words",
                    category="abstract",
                    explanation="IEEE recommends abstracts under 250 words.",
                )
            )

    for fig in formatted.figures:
        if fig.width_pct > rules.figure_max_width_pct:
            old = fig.width_pct
            fig.width_pct = rules.figure_max_width_pct
            actions.append(
                FormatAction(
                    id=f"fig-{fig.id}",
                    message=f"Resizing {fig.id} to column width",
                    category="figures",
                    explanation="IEEE format requires figures to fit within single-column width.",
                )
            )

    for i, ref in enumerate(formatted.references):
        ref.order = i + 1

    formatted.metadata["rules_applied"] = rules.name
    formatted.metadata["columns"] = rules.columns
    formatted.metadata["margins_inch"] = rules.margins_inch
    formatted.metadata["body_font"] = rules.body_font
    formatted.metadata["body_size_pt"] = rules.body_size_pt

    return formatted, actions


def document_to_plain_preview(doc: SemanticDocument) -> str:
    lines = [doc.title, ""]
    if doc.authors:
        lines.append(", ".join(a.name for a in doc.authors))
        lines.append("")
    if doc.abstract:
        lines.append("Abstract")
        lines.append(doc.abstract)
        lines.append("")
    for sec in doc.sections:
        if sec.title:
            lines.append(sec.title)
        if sec.content:
            lines.append(sec.content)
        lines.append("")
    for fig in doc.figures:
        lines.append(f"Figure: {fig.caption}")
    if doc.references:
        lines.append("References")
        for ref in sorted(doc.references, key=lambda r: r.order):
            lines.append(f"[{ref.order}] {ref.text}")
    return "\n".join(lines)
