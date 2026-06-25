"""
revision_parser.py

├── Data Models
│   ├── TableRow
│   └── Block
│
├── Content Detectors
│   ├── has_markdown_table()
│   ├── is_numbered_list()
│   ├── is_bullet_list()
│   └── is_short_dense_text()
│
├── Classifier
│   ├── classify_by_content()
│   └── apply_heading_hint()
│
├── Table Parser
│   └── parse_table()
│
├── Core Parser
│   ├── split_into_raw_blocks()
│   └── parse_block()
│
└── Entry Point
    └── parse_revision_markdown()
"""


import re
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class TableRow:
    """
    One row of a markdown table.
    cells[0] is the first column, etc.
    """

    cells: list[str]
    is_header: bool = False


@dataclass
class Block:
    """
    One semantic section of a revision chapter.

    type is determined by content shape + heading hint.
    title is the raw heading text.
    content holds either plain text lines or TableRow objects.
    raw is the original markdown string for the block body.
    """

    type: str
    title: str
    content: list[str | TableRow] = field(
        default_factory=list
    )
    raw: str = ""


# ---------------------------------------------------------------------------
# Content Detectors
# These look at the raw text of a block body only.
# They know nothing about headings or subjects.
# ---------------------------------------------------------------------------


def has_markdown_table(
    text: str
) -> bool:
    """
    True if the block contains a markdown table.

    A markdown table has at least one line matching
    the separator pattern: | --- | --- |
    """

    for line in text.splitlines():

        stripped = line.strip()

        if not stripped:
            continue

        # Separator row: cells made of dashes/colons
        if re.match(
            r"^\|[\s\-\|:]+\|$",
            stripped
        ):
            return True

    return False


def is_numbered_list(
    text: str
) -> bool:
    """
    True if the majority of non-empty lines
    are numbered list items.

    Matches: 1. / 1) / Step 1: etc.
    """

    lines = [
        l.strip()
        for l in text.splitlines()
        if l.strip()
    ]

    if not lines:
        return False

    numbered = sum(
        1 for l in lines
        if re.match(
            r"^(\d+[\.\)]|step\s+\d+:?)",
            l,
            re.IGNORECASE
        )
    )

    return (
        numbered / len(lines)
    ) >= 0.5


def is_bullet_list(
    text: str
) -> bool:
    """
    True if the majority of non-empty lines
    are bullet list items.

    Matches: - / * / • / + prefixes.
    Requires at least 2 bullets to qualify.
    """

    lines = [
        l.strip()
        for l in text.splitlines()
        if l.strip()
    ]

    if len(lines) < 2:
        return False

    bullets = sum(
        1 for l in lines
        if re.match(
            r"^[-*•+]\s",
            l
        )
    )

    return (
        bullets / len(lines)
    ) >= 0.5


def is_short_dense_text(
    text: str
) -> bool:
    """
    True if the block is a short block of prose:
    few lines, no lists, no tables.

    Used to identify definition-style blocks.
    """

    lines = [
        l.strip()
        for l in text.splitlines()
        if l.strip()
    ]

    if not lines:
        return False

    has_list = any(
        re.match(r"^[-*•+\d]", l)
        for l in lines
    )

    return (
        not has_list
        and len(lines) <= 6
    )


# ---------------------------------------------------------------------------
# Classifier
# Pass 1: content shape (subject-agnostic, always runs)
# Pass 2: heading hint  (optional upgrade, never overrides)
# ---------------------------------------------------------------------------


# Universal heading signals — domain-agnostic.
# Only words that carry clear semantic intent
# regardless of subject matter.

_HINT_MAP: dict[str, str] = {

    # tip promotion signals
    "tip":       "tips",
    "tips":      "tips",
    "hint":      "tips",
    "interview": "tips",
    "exam":      "tips",

    # warning promotion signals
    "mistake":   "tips",
    "mistakes":  "tips",
    "error":     "errors",
    "errors":    "errors",
    "avoid":     "errors",
    "warning":   "errors",
    "pitfall":   "errors",
    "pitfalls":  "errors",
    "caution":   "errors",

    # summary promotion signals
    "summary":   "summary",
    "takeaway":  "summary",
    "takeaways": "summary",
    "recap":     "summary",
    "review":    "summary",
    "overview":  "summary",

    # formula / equation signals
    "formula":   "formula",
    "formulas":  "formula",
    "equation":  "formula",
    "equations": "formula",
    "law":       "formula",
    "theorem":   "formula",
    "proof":     "formula",
}

# Only these base types are eligible for promotion.
# A table stays a table regardless of heading.
_PROMOTABLE = {
    "bullets",
    "text",
    "definition",
}


def classify_by_content(
    text: str
) -> str:
    """
    Pass 1: classify block purely by content shape.

    Order matters:
    table > steps > bullets > definition > text
    """

    if has_markdown_table(text):
        return "table"

    if is_numbered_list(text):
        return "steps"

    if is_bullet_list(text):
        return "bullets"

    if is_short_dense_text(text):
        return "definition"

    return "text"


def apply_heading_hint(
    heading: str,
    base_type: str
) -> str:
    """
    Pass 2: optionally promote base_type using
    universal heading signals.

    Only promotes — never overrides a content-derived
    type like 'table' or 'steps'.
    """

    if base_type not in _PROMOTABLE:
        return base_type

    heading_lower = heading.lower()

    words = re.findall(
        r"[a-z]+",
        heading_lower
    )

    for word in words:

        if word in _HINT_MAP:
            return _HINT_MAP[word]

    return base_type


def classify_block(
    heading: str,
    content_text: str
) -> str:
    """
    Full two-pass classification.

    Returns the final block type string.
    """

    base_type = classify_by_content(
        content_text
    )

    return apply_heading_hint(
        heading,
        base_type
    )


# ---------------------------------------------------------------------------
# Table Parser
# ---------------------------------------------------------------------------


def parse_table(
    text: str
) -> list[TableRow]:
    """
    Parse a markdown table into TableRow objects.

    Skips separator rows (| --- | --- |).
    First data row is marked as header.
    """

    rows: list[TableRow] = []
    header_found = False

    for line in text.splitlines():

        stripped = line.strip()

        if not stripped:
            continue

        # Skip separator rows
        if re.match(
            r"^\|[\s\-\|:]+\|$",
            stripped
        ):
            continue

        if not stripped.startswith("|"):
            continue

        cells = [
            c.strip()
            for c in stripped.split("|")
            if c.strip()
        ]

        if not cells:
            continue

        is_header = not header_found
        header_found = True

        rows.append(
            TableRow(
                cells=cells,
                is_header=is_header
            )
        )

    return rows


# ---------------------------------------------------------------------------
# Content line extractor
# ---------------------------------------------------------------------------


def extract_content_lines(
    text: str,
    block_type: str
) -> list[str | TableRow]:
    """
    Convert raw block text into structured content.

    For tables: returns list[TableRow].
    For everything else: returns list[str] of
    non-empty lines, stripping markdown formatting
    only lightly (preserving inline code, LaTeX, bold).
    """

    if block_type == "table":
        return parse_table(text)

    lines = []

    for line in text.splitlines():

        stripped = line.strip()

        if not stripped:
            continue

        lines.append(stripped)

    return lines


# ---------------------------------------------------------------------------
# Core Parser
# ---------------------------------------------------------------------------


def split_into_raw_blocks(
    markdown: str
) -> list[tuple[str, str]]:
    """
    Split a chapter's markdown into raw (heading, body) pairs.

    Splits on ## headings only.
    The chapter title (# heading) is excluded from blocks
    and returned separately.

    Returns list of (heading_text, body_text) tuples.
    """

    # Normalise line endings
    markdown = markdown.replace(
        "\r\n", "\n"
    )

    # Split on ## headings
    # Pattern captures the heading line and the body after it
    pattern = re.compile(
        r"^##\s+(.+)$",
        re.MULTILINE
    )

    matches = list(
        pattern.finditer(markdown)
    )

    if not matches:
        return []

    raw_blocks = []

    for i, match in enumerate(matches):

        heading = match.group(1).strip()

        body_start = match.end()

        body_end = (
            matches[i + 1].start()
            if i + 1 < len(matches)
            else len(markdown)
        )

        body = markdown[
            body_start:body_end
        ].strip()

        raw_blocks.append(
            (heading, body)
        )

    return raw_blocks


def extract_chapter_title(
    markdown: str
) -> str:
    """
    Extract the # h1 title from a chapter markdown.

    Returns empty string if not found.
    """

    match = re.search(
        r"^#\s+(.+)$",
        markdown,
        re.MULTILINE
    )

    if match:
        return match.group(1).strip()

    return ""


def parse_block(
    heading: str,
    body: str
) -> Block:
    """
    Parse one raw (heading, body) pair into a Block.
    """

    block_type = classify_block(
        heading,
        body
    )

    content = extract_content_lines(
        body,
        block_type
    )

    return Block(
        type=block_type,
        title=heading,
        content=content,
        raw=body
    )


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------


def parse_revision_markdown(
    markdown: str
) -> tuple[str, list[Block]]:
    """
    Parse a full revision chapter markdown string.

    Returns:
        chapter_title : str        — the # h1 heading
        blocks        : list[Block] — ordered semantic blocks

    Usage:
        title, blocks = parse_revision_markdown(markdown)
    """

    chapter_title = extract_chapter_title(
        markdown
    )

    raw_blocks = split_into_raw_blocks(
        markdown
    )

    blocks = [
        parse_block(heading, body)
        for heading, body
        in raw_blocks
    ]

    return chapter_title, blocks