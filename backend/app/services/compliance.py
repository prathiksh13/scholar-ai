"""IEEE compliance scoring."""

from pydantic import BaseModel

from app.models.document_schema import SemanticDocument
from app.rules.ieee import get_ieee_rules


class ComplianceIssue(BaseModel):
    id: str
    severity: str  # error | warning | info
    message: str
    explanation: str = ""


class ComplianceReport(BaseModel):
    format: str
    score: int
    issues: list[ComplianceIssue]


def run_compliance_check(doc: SemanticDocument) -> ComplianceReport:
    rules = get_ieee_rules()
    issues: list[ComplianceIssue] = []
    score = 100

    if not doc.abstract:
        issues.append(
            ComplianceIssue(
                id="no-abstract",
                severity="error",
                message="Missing abstract section",
                explanation="IEEE papers require an abstract.",
            )
        )
        score -= 15
    elif len(doc.abstract.split()) > rules.abstract_max_words:
        issues.append(
            ComplianceIssue(
                id="abstract-length",
                severity="warning",
                message="Abstract exceeds word limit",
                explanation=f"IEEE recommends ≤ {rules.abstract_max_words} words.",
            )
        )
        score -= 8

    for fig in doc.figures:
        if fig.width_pct > rules.figure_max_width_pct:
            issues.append(
                ComplianceIssue(
                    id=f"fig-width-{fig.id}",
                    severity="warning",
                    message=f"{fig.id}: figure exceeds column width",
                    explanation="Figures should fit single-column width in IEEE format.",
                )
            )
            score -= 5

    if doc.references:
        orders = [r.order for r in doc.references]
        if orders != sorted(orders) or orders != list(range(1, len(orders) + 1)):
            issues.append(
                ComplianceIssue(
                    id="ref-order",
                    severity="warning",
                    message="References not properly ordered",
                    explanation="IEEE uses numeric references in order of citation.",
                )
            )
            score -= 10
    else:
        issues.append(
            ComplianceIssue(
                id="no-refs",
                severity="info",
                message="No references detected",
                explanation="Add a References section for completeness.",
            )
        )
        score -= 5

    if not doc.title:
        issues.append(
            ComplianceIssue(
                id="no-title",
                severity="error",
                message="Missing paper title",
                explanation="Title is required for IEEE submissions.",
            )
        )
        score -= 12

    score = max(0, min(100, score))
    return ComplianceReport(
        format=doc.format_target or "IEEE",
        score=score,
        issues=issues,
    )
