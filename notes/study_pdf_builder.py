import json
import logging
import re
from pathlib import Path

from pydantic import BaseModel
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import (
    ParagraphStyle,
    getSampleStyleSheet
)
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle
)


logging.basicConfig(
    level=logging.INFO,
    format=
    "%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

# constants

NOTES_DIR = Path(
        "outputs/notes"
)

SCREENSHOTS_DIR = Path(
        "outputs/screenshots/selected"
)

PDF_OUT_DIR = Path(
        "outputs/pdf"
)

OUTLINE_PATH = (

    NOTES_DIR
    / "lecture_outline.json"
)

PDF_OUT_PATH = (

    PDF_OUT_DIR
    / "study_notes.pdf"
)

MAX_IMAGES_PER_CHAPTER = 3

IMAGE_MAX_WIDTH = 5.5 * inch

IMAGE_MAX_HEIGHT = 3.5 * inch


# Models


class ScreenshotEntry(BaseModel):

    path: str

    reason: str

    section: str

    importance: int


class ChapterScreenshots(BaseModel):

    chapter_id: int

    screenshots: list[ScreenshotEntry]


class ChapterOutline(BaseModel):

    chapter_id: int

    title: str

    focus_concepts: list[str] = []


class LectureOutline(BaseModel):

    lecture_title: str

    chapters: list[ChapterOutline]


# Styles


def build_styles():
    """
    Build and return the paragraph style sheet used
    throughout the document.
    """

    styles = getSampleStyleSheet()

    styles.add(

        ParagraphStyle(

            name="CoverTitle",
            parent=styles["Title"],
            fontSize=28,
            leading=34,
            alignment=TA_CENTER,
            spaceAfter=24
        )
    )

    styles.add(

        ParagraphStyle(

            name="CoverSubtitle",
            parent=styles["Normal"],
            fontSize=14,
            leading=18,
            alignment=TA_CENTER,
            textColor="#555555",
            spaceAfter=6
        )
    )

    styles.add(

        ParagraphStyle(

            name="ChapterHeading",
            parent=styles["Heading1"],
            fontSize=20,
            leading=26,
            spaceAfter=4
        )
    )

    styles.add(

        ParagraphStyle(

            name="ChapterLabel",
            parent=styles["Normal"],
            fontSize=11,
            textColor="#888888",
            spaceAfter=14
        )
    )

    styles.add(

        ParagraphStyle(

            name="BodyHeading2",
            parent=styles["Heading2"],
            fontSize=15,
            spaceBefore=14,
            spaceAfter=8
        )
    )

    styles.add(

        ParagraphStyle(

            name="BodyHeading3",
            parent=styles["Heading3"],
            fontSize=12.5,
            spaceBefore=10,
            spaceAfter=6
        )
    )

    styles.add(

        ParagraphStyle(

            name="BodyHeading4",
            parent=styles["Heading4"],
            fontSize=11,
            spaceBefore=8,
            spaceAfter=5
        )
    )

    styles.add(

        ParagraphStyle(

            name="TableHeaderCell",
            parent=styles["BodyText"],
            fontSize=10,
            leading=13,
            fontName="Helvetica-Bold"
        )
    )

    styles.add(

        ParagraphStyle(

            name="TableBodyCell",
            parent=styles["BodyText"],
            fontSize=10,
            leading=13
        )
    )

    styles.add(

        ParagraphStyle(

            name="BodyText2",
            parent=styles["BodyText"],
            fontSize=10.5,
            leading=15,
            spaceAfter=8
        )
    )

    styles.add(

        ParagraphStyle(

            name="BulletText",
            parent=styles["BodyText"],
            fontSize=10.5,
            leading=15,
            leftIndent=18,
            bulletIndent=6,
            spaceAfter=4
        )
    )

    styles.add(

        ParagraphStyle(

            name="VisualsHeading",
            parent=styles["Heading2"],
            fontSize=15,
            spaceBefore=20,
            spaceAfter=10
        )
    )

    styles.add(

        ParagraphStyle(

            name="ImageCaption",
            parent=styles["Normal"],
            fontSize=10,
            leading=13,
            textColor="#333333",
            spaceBefore=6
        )
    )

    styles.add(

        ParagraphStyle(

            name="ImageReason",
            parent=styles["Normal"],
            fontSize=9.5,
            leading=12,
            textColor="#777777",
            spaceAfter=16
        )
    )

    return styles


# Markdown -> reportlab text conversion


MATH_VARIABLE_PATTERN = re.compile(

    r"\b([A-Za-z])\b"

)

FRAC_PATTERN = re.compile(

    r"\\frac\{([^{}]+)\}\{([^{}]+)\}"

)

TEXT_COMMAND_PATTERN = re.compile(

    r"\\text\{([^{}]+)\}"

)


def strip_text_commands(

    segment

):
    """
    Replace \\text{...} with its plain inner content. \\text is
    LaTeX's escape hatch for putting normal words inside a math
    expression, so the wrapper itself carries no meaning here.
    """

    return TEXT_COMMAND_PATTERN.sub(

        r"\1",
        segment

    )


def convert_fractions(

    segment

):
    """
    Convert \\frac{a}{b} into an inline "(a) / (b)" rendering.
    True stacked fractions aren't practical in flowing
    Paragraph text, so this keeps the formula readable on one
    line instead of leaving raw LaTeX in place. Both the
    numerator and denominator are parenthesized so multi-term
    expressions like \\frac{start + end}{2} don't read as
    ambiguous once flattened to one line.
    """

    return FRAC_PATTERN.sub(

        r"((\1) / (\2))",
        segment

    )


FLOOR_PATTERN = re.compile(

    r"\\lfloor\s*(.+?)\s*\\rfloor"

)

CEIL_PATTERN = re.compile(

    r"\\lceil\s*(.+?)\s*\\rceil"

)


def convert_floor_ceil(

    segment

):
    """
    Convert \\lfloor x \\rfloor and \\lceil x \\rceil into
    floor(x) / ceil(x) notation. The actual floor/ceiling
    bracket glyphs are not reliably present in the base PDF
    fonts reportlab uses, so this avoids missing-glyph boxes
    in the rendered PDF.
    """

    text = FLOOR_PATTERN.sub(

        r"floor(\1)",
        segment

    )

    text = CEIL_PATTERN.sub(

        r"ceil(\1)",
        text

    )

    return text


def convert_math_segment(

    segment

):
    """
    Convert a single math segment (LaTeX-style commands) into
    reportlab markup. Keeps the formula readable as styled
    inline text rather than leaving raw LaTeX commands visible.
    """

    text = segment

    text = strip_text_commands(

        text

    )

    text = convert_floor_ceil(

        text

    )

    text = convert_fractions(

        text

    )

    replacements = [

        (r"\infty", "\u221e"),
        (r"\cdot", "\u00b7"),
        (r"\times", "\u00d7"),
        (r"\le", "\u2264"),
        (r"\ge", "\u2265"),
        (r"\neq", "\u2260"),
        (r"\pm", "\u00b1"),
        (r"\to", "\u2192"),
        (r"\log", "log"),
        (r"\min", "min"),
        (r"\max", "max"),
        (r"\sum", "\u03a3"),

    ]

    for latex, replacement in replacements:

        text = text.replace(

            latex,
            replacement

        )

    text = MATH_VARIABLE_PATTERN.sub(

        r"<i>\1</i>",
        text

    )

    return text


def convert_inline_math(

    text

):
    """
    Replace $...$ segments with styled inline reportlab markup.
    """

    def replace(

        match

    ):

        inner = match.group(

            1

        )

        return convert_math_segment(

            inner

        )

    return re.sub(

        r"\$(.+?)\$",
        replace,
        text

    )


BARE_LATEX_PATTERN = re.compile(

    r"\\(?:frac\{[^{}]+\}\{[^{}]+\}"
    r"|text\{[^{}]+\}"
    r"|lfloor|rfloor|lceil|rceil"
    r"|infty|cdot|times|le|ge|neq|pm|to"
    r"|log|min|max|sum)"

)


def convert_bare_latex_commands(

    text

):
    """
    Convert LaTeX commands that appear outside of $...$
    delimiters. Some generated notes emit bare commands like
    \\infty or \\frac{a}{b} directly in prose without wrapping
    them in math delimiters at all. This only touches text that
    matches a known LaTeX command token, so plain prose is left
    untouched, unlike convert_math_segment which also
    italicizes bare variables and would be unsafe to run over
    an entire line.
    """

    if not BARE_LATEX_PATTERN.search(

        text

    ):

        return text

    converted = strip_text_commands(

        text

    )

    converted = convert_floor_ceil(

        converted

    )

    converted = convert_fractions(

        converted

    )

    replacements = [

        (r"\infty", "\u221e"),
        (r"\cdot", "\u00b7"),
        (r"\times", "\u00d7"),
        (r"\le", "\u2264"),
        (r"\ge", "\u2265"),
        (r"\neq", "\u2260"),
        (r"\pm", "\u00b1"),
        (r"\to", "\u2192"),
        (r"\log", "log"),
        (r"\min", "min"),
        (r"\max", "max"),
        (r"\sum", "\u03a3"),

    ]

    for latex, replacement in replacements:

        converted = converted.replace(

            latex,
            replacement

        )

    return converted


def escape_xml(

    text

):
    """
    Escape raw XML-special characters before any reportlab
    markup is injected, so user content can never break the
    Paragraph mini-XML parser.
    """

    return (

        text

        .replace("&", "&amp;")

        .replace("<", "&lt;")

        .replace(">", "&gt;")
    )


def convert_inline_code(

    text

):
    """
    Convert `code` spans into monospace reportlab markup.
    """

    return re.sub(

        r"`([^`]+)`",
        r'<font face="Courier">\1</font>',
        text

    )


def convert_inline_markdown(

    text

):
    """
    Convert a single line of markdown text into reportlab
    Paragraph markup: bold, italic, inline code, and math.
    """

    escaped = escape_xml(

        text

    )

    with_math = convert_inline_math(

        escaped

    )

    with_bare_latex = convert_bare_latex_commands(

        with_math

    )

    with_code = convert_inline_code(

        with_bare_latex

    )

    bolded = re.sub(

        r"\*\*(.+?)\*\*",
        r"<b>\1</b>",
        with_code

    )

    italicized = re.sub(

        r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)",
        r"<i>\1</i>",
        bolded

    )

    return italicized


# Loading


def load_outline(

    path

):
    """
    Load and validate lecture_outline.json.
    """

    with open(

        path,
        "r",
        encoding="utf-8"

    ) as f:

        data = json.load(

            f

        )

    return LectureOutline(

        **data

    )


def load_chapter_notes(

    chapter_id

):
    """
    Load the raw markdown content for a chapter.
    Returns None if the file does not exist.
    """

    path = (

        NOTES_DIR
        / f"chapter_{chapter_id}.md"
    )

    if not path.exists():

        logger.error(

            f"Missing notes for chapter "
            f"{chapter_id}"
            f": "
            f"{path}"
        )

        return None

    with open(

        path,
        "r",
        encoding="utf-8"

    ) as f:

        return f.read()


def load_screenshot_selection(

    chapter_id

):
    """
    Load the screenshot selection for a chapter.
    Returns an empty ChapterScreenshots if the file is missing.
    """

    path = (

        SCREENSHOTS_DIR
        / f"chapter_{chapter_id}_screenshots.json"
    )

    if not path.exists():

        logger.info(

            f"No screenshot selection for chapter "
            f"{chapter_id}"
            f", continuing without images."
        )

        return ChapterScreenshots(

            chapter_id=chapter_id,
            screenshots=[]
        )

    with open(

        path,
        "r",
        encoding="utf-8"

    ) as f:

        data = json.load(

            f

        )

    return ChapterScreenshots(

        **data

    )


# Cover page


def create_cover_page(

    outline,
    styles

):
    """
    Build the cover page flowables.
    """

    story = []

    story.append(

        Spacer(
            1,
            2 * inch
        )
    )

    story.append(

        Paragraph(

            escape_xml(
                outline.lecture_title
            ),
            styles["CoverTitle"]
        )
    )

    story.append(

        Paragraph(

            "Generated by NorAI",
            styles["CoverSubtitle"]
        )
    )

    story.append(

        Spacer(
            1,
            0.6 * inch
        )
    )

    story.append(

        HRFlowable(

            width="60%",
            thickness=1,
            color="#cccccc",
            hAlign="CENTER"
        )
    )

    story.append(

        Spacer(
            1,
            0.4 * inch
        )
    )

    story.append(

        Paragraph(

            "Contents",
            styles["BodyHeading2"]
        )
    )

    toc_rows = []

    for chapter in outline.chapters:

        toc_rows.append(

            [

                Paragraph(

                    f"{chapter.chapter_id}.",
                    styles["BodyText2"]

                ),

                Paragraph(

                    escape_xml(
                        chapter.title
                    ),
                    styles["BodyText2"]

                )

            ]
        )

    toc_table = Table(

        toc_rows,
        colWidths=[
            0.4 * inch,
            5.6 * inch
        ]
    )

    toc_table.setStyle(

        TableStyle(

            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6)
            ]
        )
    )

    story.append(

        toc_table

    )

    story.append(

        PageBreak()

    )

    return story


# Chapter content


TABLE_ROW_PATTERN = re.compile(

    r"^\|(.+)\|$"

)

TABLE_SEPARATOR_PATTERN = re.compile(

    r"^\|?[\s:|-]+\|?$"

)


def is_table_row(

    line

):
    """
    Check whether a line looks like a markdown table row, e.g.
    "| a | b | c |".
    """

    return bool(

        TABLE_ROW_PATTERN.match(

            line

        )
    )


def is_table_separator(

    line

):
    """
    Check whether a line is a markdown table header separator,
    e.g. "| :--- | :--- |".
    """

    return bool(

        TABLE_SEPARATOR_PATTERN.match(

            line

        )
    ) and "-" in line


def split_table_row(

    line

):
    """
    Split a markdown table row into its individual cell strings.
    """

    inner = line.strip().strip(

        "|"

    )

    return [

        cell.strip()
        for cell in inner.split("|")

    ]


def build_table_flowable(

    table_lines,
    styles

):
    """
    Convert a contiguous block of markdown table lines (header,
    separator, body rows) into a reportlab Table flowable.
    """

    header_cells = split_table_row(

        table_lines[0]

    )

    body_rows = [

        split_table_row(row)
        for row in table_lines[2:]

    ]

    rows = []

    header_row = [

        Paragraph(

            convert_inline_markdown(cell),
            styles["TableHeaderCell"]

        )
        for cell in header_cells

    ]

    rows.append(

        header_row

    )

    for body_row in body_rows:

        rendered_row = [

            Paragraph(

                convert_inline_markdown(cell),
                styles["TableBodyCell"]

            )
            for cell in body_row

        ]

        rows.append(

            rendered_row

        )

    table = Table(

        rows,
        repeatRows=1

    )

    table.setStyle(

        TableStyle(

            [
                ("BACKGROUND", (0, 0), (-1, 0), "#eeeeee"),
                ("GRID", (0, 0), (-1, -1), 0.5, "#cccccc"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4)
            ]
        )
    )

    return table


def parse_markdown_lines(

    markdown_text,
    styles

):
    """
    Convert raw chapter markdown into a list of flowables.
    Handles headings, bullets, tables, and plain paragraphs.
    This is a pragmatic line-based parser, not a full markdown
    engine.
    """

    flowables = []

    raw_lines = markdown_text.split(

        "\n"

    )

    lines = [

        raw_line.strip()
        for raw_line in raw_lines

    ]

    total = len(

        lines

    )

    index = 0

    while index < total:

        line = lines[index]

        if not line:

            index += 1

            continue

        is_table_start = (

            is_table_row(line)
            and index + 1 < total
            and is_table_separator(lines[index + 1])
        )

        if is_table_start:

            table_lines = [

                line,
                lines[index + 1]

            ]

            lookahead = index + 2

            while (

                lookahead < total
                and is_table_row(lines[lookahead])

            ):

                table_lines.append(

                    lines[lookahead]

                )

                lookahead += 1

            flowables.append(

                build_table_flowable(

                    table_lines,
                    styles

                )
            )

            flowables.append(

                Spacer(
                    1,
                    8
                )
            )

            index = lookahead

            continue

        if line.startswith("#### "):

            content = convert_inline_markdown(

                line[5:]

            )

            flowables.append(

                Paragraph(
                    content,
                    styles["BodyHeading4"]
                )
            )

        elif line.startswith("### "):

            content = convert_inline_markdown(

                line[4:]

            )

            flowables.append(

                Paragraph(
                    content,
                    styles["BodyHeading3"]
                )
            )

        elif line.startswith("## "):

            content = convert_inline_markdown(

                line[3:]

            )

            flowables.append(

                Paragraph(
                    content,
                    styles["BodyHeading2"]
                )
            )

        elif line.startswith("# "):

            # Chapter-level H1 inside the markdown is skipped
            # here, the chapter heading is rendered separately
            # from the outline title.

            pass

        elif line.startswith("* ") or line.startswith("- "):

            content = convert_inline_markdown(

                line[2:]

            )

            flowables.append(

                Paragraph(
                    content,
                    styles["BulletText"],
                    bulletText="\u2022"
                )
            )

        else:

            content = convert_inline_markdown(

                line

            )

            flowables.append(

                Paragraph(
                    content,
                    styles["BodyText2"]
                )
            )

        index += 1

    return flowables


def create_chapter_section(

    chapter,
    markdown_text,
    styles

):
    """
    Build the flowables for a single chapter's notes section,
    including the chapter heading.
    """

    story = []

    story.append(

        Paragraph(

            f"Chapter {chapter.chapter_id}",
            styles["ChapterLabel"]
        )
    )

    story.append(

        Paragraph(

            escape_xml(
                chapter.title
            ),
            styles["ChapterHeading"]
        )
    )

    story.append(

        HRFlowable(

            width="100%",
            thickness=0.5,
            color="#dddddd",
            spaceAfter=12
        )
    )

    story.extend(

        parse_markdown_lines(

            markdown_text,
            styles

        )
    )

    return story


def add_chapter_images(

    selection,
    styles

):
    """
    Build the "Important Visuals" section for a chapter using
    its selected screenshots. Returns an empty list if there
    are no usable screenshots.
    """

    ranked = sorted(

        selection.screenshots,
        key=lambda s: s.importance,
        reverse=True

    )

    top_screenshots = ranked[

        :MAX_IMAGES_PER_CHAPTER

    ]

    usable = [

        s
        for s in top_screenshots
        if Path(s.path).exists()

    ]

    if not usable:

        return []

    story = []

    story.append(

        Paragraph(

            "Important Visuals",
            styles["VisualsHeading"]
        )
    )

    for screenshot in usable:

        try:

            image = Image(

                screenshot.path,
                width=IMAGE_MAX_WIDTH,
                height=IMAGE_MAX_HEIGHT,
                kind="proportional"
            )

        except Exception as e:

            logger.error(

                f"Failed to load image "
                f"{screenshot.path}"
                f": "
                f"{e}"
            )

            continue

        image.hAlign = "CENTER"

        story.append(

            image

        )

        story.append(

            Paragraph(

                escape_xml(
                    screenshot.section
                ),
                styles["ImageCaption"]
            )
        )

        story.append(

            Paragraph(

                escape_xml(
                    screenshot.reason
                ),
                styles["ImageReason"]
            )
        )

    return story


# Build


def build_pdf(

    outline,
    styles

):
    """
    Assemble the full document story across all chapters and
    write the final PDF to disk.
    """

    story = []

    story.extend(

        create_cover_page(

            outline,
            styles

        )
    )

    total = len(

        outline.chapters

    )

    for index, chapter in enumerate(

        outline.chapters

    ):

        markdown_text = load_chapter_notes(

            chapter.chapter_id

        )

        if markdown_text is None:

            continue

        selection = load_screenshot_selection(

            chapter.chapter_id

        )

        story.extend(

            create_chapter_section(

                chapter,
                markdown_text,
                styles

            )
        )

        story.extend(

            add_chapter_images(

                selection,
                styles

            )
        )

        if index < total - 1:

            story.append(

                PageBreak()

            )

    PDF_OUT_DIR.mkdir(

        parents=True,
        exist_ok=True
    )

    doc = SimpleDocTemplate(

        str(PDF_OUT_PATH),
        pagesize=letter,
        topMargin=0.9 * inch,
        bottomMargin=0.9 * inch,
        leftMargin=0.9 * inch,
        rightMargin=0.9 * inch
    )

    doc.build(

        story

    )

    logger.info(

        f"Saved PDF to "
        f"{PDF_OUT_PATH}"
    )


def main():

    logger.info(

        "Starting study PDF build."
    )

    outline = load_outline(

        OUTLINE_PATH

    )

    styles = build_styles()

    build_pdf(

        outline,
        styles

    )

    logger.info(

        "Study PDF build complete."
    )


if __name__ == "__main__":

    main()