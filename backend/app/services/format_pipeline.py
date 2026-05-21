"""Live formatting pipeline with step logs."""

import asyncio
import json
from pathlib import Path
from typing import AsyncGenerator

from app.rules.ieee import IEEE_FORMAT_STEPS, get_ieee_rules
from app.services.compliance import run_compliance_check
from app.services.renderer import render_semantic_to_docx
from app.services.rules_engine import apply_format_rules
from app.services.semantic_parser import parse_document_to_semantic
from app.services import formatflow_store as store


async def stream_format_job(document_id: str, format_name: str = "IEEE") -> AsyncGenerator[str, None]:
    """SSE stream of formatting steps."""
    record = store.get_record(document_id)
    if not record:
        yield _sse("error", {"message": "Document not found"})
        return

    path = Path(record["file_path"])
    filename = record["filename"]
    # try to reuse any already-parsed semantic to avoid re-parsing in-stream
    semantic = store.get_semantic(document_id)
    rules = None

    for step_id, message, explanation in IEEE_FORMAT_STEPS:
        yield _sse(
            "log",
            {
                "id": step_id,
                "message": message,
                "status": "running",
                "explanation": explanation,
            },
        )
        await asyncio.sleep(0.35)

        if step_id == "parse":
            if not semantic:
                semantic = parse_document_to_semantic(path, document_id, filename)
            else:
                # already parsed by background task
                pass
            semantic.metadata["columns"] = 1
            semantic.metadata["body_font"] = "Times New Roman"
            semantic.metadata["body_size_pt"] = 10
            semantic.metadata["margins_inch"] = 0.75
            store.save_semantic(document_id, semantic)
            yield _sse(
                "preview",
                {
                    "step": step_id,
                    "message": "Building semantic preview...",
                    "explanation": "The document structure is ready and can now be mapped into IEEE rules.",
                    "html": semantic.to_editor_html(),
                    "semantic": semantic.model_dump(),
                },
            )

        elif semantic:
            rules = rules or get_ieee_rules()

            if step_id == "abstract":
                semantic.metadata["abstract_detected"] = bool(semantic.abstract)

            elif step_id == "headings":
                semantic.metadata["heading_count"] = len(
                    [s for s in semantic.sections if s.title or s.type == "heading"]
                )

            elif step_id == "margins":
                semantic.metadata["margins_inch"] = rules.margins_inch

            elif step_id == "fonts":
                semantic.metadata["body_font"] = rules.body_font
                semantic.metadata["body_size_pt"] = rules.body_size_pt

            elif step_id == "columns":
                semantic.metadata["columns"] = rules.columns

            elif step_id == "figures":
                for fig in semantic.figures:
                    fig.width_pct = min(fig.width_pct, rules.figure_max_width_pct)
                    fig.position = "inline"

            elif step_id == "captions":
                semantic.metadata["captions"] = "normalized"

            elif step_id == "references":
                for index, ref in enumerate(sorted(semantic.references, key=lambda r: r.order), start=1):
                    ref.order = index

            elif step_id == "spacing":
                semantic.metadata["line_spacing"] = rules.line_spacing

            if step_id in {"abstract", "headings", "margins", "fonts", "columns", "figures", "captions", "references", "spacing"}:
                yield _sse(
                    "preview",
                    {
                        "step": step_id,
                        "message": message,
                        "explanation": explanation,
                        "html": semantic.to_editor_html(),
                        "semantic": semantic.model_dump(),
                    },
                )

            if step_id == "compliance":
                report = run_compliance_check(semantic)
                store.save_compliance(document_id, report)
                yield _sse("compliance", report.model_dump())

        yield _sse(
            "log",
            {
                "id": step_id,
                "message": message.replace("...", ""),
                "status": "done",
            },
        )

    semantic = semantic or store.get_semantic(document_id)
    if semantic:
        formatted, actions = apply_format_rules(semantic, format_name)
        store.save_formatted(document_id, formatted, actions)
        report = run_compliance_check(formatted)
        store.save_compliance(document_id, report)

        yield _sse(
            "preview",
            {
                "step": "final",
                "message": f"{format_name.upper()} formatting complete.",
                "explanation": "The live preview now reflects the finalized IEEE rules and is ready for editing.",
                "html": formatted.to_editor_html(),
                "semantic": formatted.model_dump(),
            },
        )

        out_path = render_semantic_to_docx(formatted, document_id)
        store.set_output_path(document_id, str(out_path))

        yield _sse(
            "complete",
            {
                "document_id": document_id,
                "html": formatted.to_editor_html(),
                "semantic": formatted.model_dump(),
                "plain": formatted.title,
                "compliance": report.model_dump(),
                "actions": [
                    {
                        "id": a.id,
                        "message": a.message,
                        "category": a.category,
                        "explanation": a.explanation,
                    }
                    for a in actions
                ],
            },
        )


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"
