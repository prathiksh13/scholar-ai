"""IEEE conference/journal formatting rules."""

from dataclasses import dataclass, field


@dataclass
class IEEERules:
    name: str = "IEEE"
    margins_inch: float = 0.75
    body_font: str = "Times New Roman"
    body_size_pt: int = 10
    title_size_pt: int = 24
    heading_sizes_pt: tuple[int, ...] = (12, 11, 10)
    line_spacing: float = 1.0
    columns: int = 2
    column_gap_inch: float = 0.25
    abstract_max_words: int = 250
    figure_max_width_pct: float = 100.0  # single column
    figure_caption_below: bool = True
    table_caption_above: bool = True
    reference_style: str = "numeric"
    title_centered: bool = True
    keywords_required: bool = False


IEEE_RULES = IEEERules()


@dataclass
class FormatAction:
    id: str
    message: str
    category: str
    explanation: str = ""
    applied: bool = True


IEEE_FORMAT_STEPS: list[tuple[str, str, str]] = [
    ("parse", "Detecting title and structure...", "Semantic parser extracts title, sections, and metadata."),
    ("abstract", "Detecting abstract...", "IEEE papers require a clearly labeled abstract section."),
    ("headings", "Extracting headings...", "Heading hierarchy is mapped to IEEE section levels."),
    ("margins", "Applying IEEE margins (0.75 in)...", "IEEE specifies 0.75 inch margins on all sides."),
    ("fonts", "Applying Times New Roman 10pt body text...", "IEEE body text uses 10pt Times New Roman."),
    ("columns", "Creating two-column layout...", "IEEE conference format uses two columns after the title block."),
    ("figures", "Resizing figures to fit single-column width...", "Figures must fit within single-column width."),
    ("captions", "Aligning figure and table captions...", "Captions follow IEEE placement rules."),
    ("references", "Converting references to IEEE numeric style...", "References are numbered in order of appearance."),
    ("spacing", "Adjusting paragraph spacing...", "IEEE uses single spacing with minimal extra space."),
    ("compliance", "Running compliance check...", "Validates margins, abstract length, and reference order."),
]


def get_ieee_rules() -> IEEERules:
    return IEEE_RULES
