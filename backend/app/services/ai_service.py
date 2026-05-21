import json
import re

from app.config import OPENAI_API_KEY
from app.services.formatter import FORMAT_STYLES

DEFAULT_SUGGESTIONS = [
    {"category": "Margins", "message": "Set uniform 1-inch margins on all sides."},
    {"category": "Spacing", "message": "Apply double-spacing for body paragraphs where required."},
    {"category": "Citations", "message": "Normalize in-text citations to the target style."},
    {"category": "Headings", "message": "Use consistent heading hierarchy (H1 → H2 → H3)."},
]


def get_ai_suggestions(text: str, fmt: str) -> list[dict]:
    if not text.strip():
        return DEFAULT_SUGGESTIONS

    if OPENAI_API_KEY:
        try:
            return _openai_suggestions(text, fmt)
        except Exception:
            pass

    return _rule_based_suggestions(text, fmt)


def _openai_suggestions(text: str, fmt: str) -> list[dict]:
    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)
    sample = text[:4000]

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an academic formatting assistant. "
                    "Return JSON array of objects with keys: category, message. "
                    "Categories: Margins, Spacing, Citations, Headings, Structure. "
                    "Provide 4-6 specific, actionable suggestions."
                ),
            },
            {
                "role": "user",
                "content": f"Target format: {fmt}\n\nDocument excerpt:\n{sample}",
            },
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
    )

    content = response.choices[0].message.content or "{}"
    data = json.loads(content)
    items = data.get("suggestions", data.get("items", data))
    if isinstance(items, list) and items:
        return [
            {"category": s.get("category", "General"), "message": s.get("message", str(s))}
            for s in items[:6]
        ]
    return _rule_based_suggestions(text, fmt)


def _rule_based_suggestions(text: str, fmt: str) -> list[dict]:
    style = FORMAT_STYLES.get(fmt.upper(), FORMAT_STYLES["IEEE"])
    suggestions = [
        {
            "category": "Margins",
            "message": f"Apply {style['margin']}-inch margins per {fmt} guidelines.",
        },
        {
            "category": "Spacing",
            "message": f"Set line spacing to {style['line_spacing']} for body text.",
        },
        {
            "category": "Citations",
            "message": f"Use {fmt}-style citations such as {style['citation']}.",
        },
        {
            "category": "Headings",
            "message": "Ensure section titles follow a clear hierarchical order.",
        },
    ]

    if not re.search(r"\babstract\b", text, re.I):
        suggestions.append({
            "category": "Structure",
            "message": "Consider adding an Abstract section after the title.",
        })
    if not re.search(r"\breferences?\b", text, re.I):
        suggestions.append({
            "category": "Structure",
            "message": "Add a References section for bibliography entries.",
        })
    if len(text.split()) < 200:
        suggestions.append({
            "category": "Structure",
            "message": "Document appears short — verify all required sections are present.",
        })

    return suggestions[:6]
