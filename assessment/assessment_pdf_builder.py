"""
assessment_pdf_builder.py

├── Config (assessment-specific additions)
├── AssessmentPDF        (subclasses RevisionPDF)
│   ├── add_assessment_cover_page()
│   ├── draw_question_block()       (dispatcher by Question.type)
│   ├── _draw_mcq_options()
│   ├── _draw_true_false_options()
│   ├── _draw_lined_answer_space()
│   ├── _difficulty_badge()
│   ├── _estimate_question_block_h()
│   ├── add_answer_key_divider()
│   └── draw_answer_key_entry()
│
└── Entry Point
    └── build_assessment_pdf()

Design notes:

- AssessmentPDF subclasses RevisionPDF (from revision_pdf_builder.py)
  rather than duplicating it, per the decision to reuse the existing
  brand exactly: same palette constants, fonts, card-shell drawing,
  page-break logic, cover page, and chapter divider all come for free.
  Only assessment-specific rendering (question blocks, answer options,
  the answer key) is new here.

- Per the confirmed design: this PDF shows QUESTIONS ONLY in the main
  body. A separate "Answer Key" section at the end (one per chapter,
  in question order) holds every answer + explanation. This means a
  student can use the main body as an actual worksheet without seeing
  answers leak through, and flip to the back to self-check.

- MCQ and True/False render as lettered circles (A/B/C/D), matching
  the confirmed exam-style preference and visually echoing
  draw_steps_card's numbered-circle pattern from revision_pdf_builder
  — same mechanism, different glyph and color, so it doesn't read as
  literally the same card type.

- Every other type (Short Answer, Long Answer, Conceptual, Application,
  Code Tracing, Complexity, Scenario, Fill in the Blank) gets ruled
  blank lines sized by type — Long Answer gets more lines than Short
  Answer, Fill in the Blank gets a single short line. This is a
  judgment call with no source-of-truth from the design doc; the line
  counts in _LINES_BY_TYPE are a reasonable starting point and the
  first thing to tune after seeing real output.

- Difficulty badges reuse color associations already established in
  the revision deck: green/amber/red already mean
  summary/tip/watch-out there. Easy -> COLOR_SUMMARY_ACC (green),
  Medium -> COLOR_TIPS_ACC (amber), Hard -> COLOR_ERRORS_ACC (red).
  This isn't a coincidence carried over from a different meaning —
  green-for-safe/red-for-caution is a generically reasonable mapping
  for difficulty too, so reusing it is intentional, not just lazy.
"""

import json
from pathlib import Path

from revision_notes.revision_pdf_builder import (
    RevisionPDF,
    MARGIN,
    CARD_W,
    CARD_PAD,
    CARD_GAP,
    CARD_RADIUS,
    LINE_H_BODY,
    FONT_REGULAR,
    FONT_BOLD,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_MUTED,
    COLOR_PAGE_BG,
    COLOR_SUMMARY_ACC,
    COLOR_TIPS_ACC,
    COLOR_ERRORS_ACC,
    COLOR_STEPS_BG,
    COLOR_STEPS_BD,
    COLOR_DEFINITION_ACC,
    COLOR_TEXT_CARD_BG,
    COLOR_TEXT_CARD_BD,
    _strip_markdown_inline,
)
from assessment.assessment_models import Assessment, Question


# ---------------------------------------------------------------------------
# Assessment-specific config
# ---------------------------------------------------------------------------

# Difficulty -> accent color, reusing existing revision-deck associations.
DIFFICULTY_COLORS = {
    "Easy": COLOR_SUMMARY_ACC,
    "Medium": COLOR_TIPS_ACC,
    "Hard": COLOR_ERRORS_ACC,
}

# Question-block background/border — distinct from revision cards
# (plain neutral card, the badge + lettered options carry the color)
COLOR_QUESTION_BG = (255, 255, 255)
COLOR_QUESTION_BD = (215, 213, 208)

# MCQ / True-False lettered circle colors — close to but distinct from
# COLOR_STEPS_NUM_BG (steps cards), so MCQ doesn't read as a steps card.
COLOR_OPTION_CIRCLE_BG = (90, 70, 180)
COLOR_OPTION_CIRCLE_TEXT = (255, 255, 255)

# Ruled-line color for free-response answer space.
COLOR_RULED_LINE = (205, 203, 198)

RULED_LINE_GAP = 7.0  # vertical spacing between ruled lines, mm

# Default number of ruled lines per question type for free-response
# questions. Not derived from anywhere in the design doc — a starting
# point to tune once real output is reviewed.
_LINES_BY_TYPE = {
    "Fill in the Blank": 1,
    "Short Answer": 3,
    "Long Answer": 6,
    "Conceptual": 4,
    "Application": 4,
    "Code Tracing": 5,
    "Complexity": 3,
    "Scenario": 4,
}
_DEFAULT_LINES = 3

_MCQ_LETTERS = ["A", "B", "C", "D", "E", "F"]


# ---------------------------------------------------------------------------
# AssessmentPDF
# ---------------------------------------------------------------------------

class AssessmentPDF(RevisionPDF):

    def _cover_strip_items(self, metadata) -> list[str]:
        """
        Override RevisionPDF's metadata strip builder: AssessmentMetadata
        uses estimated_time (not estimated_read_time, which doesn't
        exist on this model — using the base implementation unmodified
        would have silently dropped the read-time entirely, since
        _meta_get() returns None for a missing field name rather than
        raising). Also adds a question count, which RevisionMetadata
        has no equivalent of.
        """
        total_chapters  = self._meta_get(metadata, "total_chapters", None)
        total_questions = self._meta_get(metadata, "total_questions", None)
        estimated_time   = self._meta_get(metadata, "estimated_time", None)
        generated_at     = self._meta_get(metadata, "generated_at", "")

        strip_items = []
        if total_chapters is not None:
            label = "Chapter" if total_chapters == 1 else "Chapters"
            strip_items.append(f"{total_chapters} {label}")
        if total_questions is not None:
            label = "Question" if total_questions == 1 else "Questions"
            strip_items.append(f"{total_questions} {label}")
        if estimated_time is not None:
            strip_items.append(f"~{estimated_time} min")
        date_str = self._format_generated_at(generated_at)
        if date_str:
            strip_items.append(date_str)

        return strip_items


    #
    # RevisionPDF._estimate_multiline_h (inherited) uses a character-
    # count heuristic calibrated for revision_pdf_builder's own card
    # text. Testing against real assessment_generator.py output showed
    # it overestimates height by roughly 2x on longer strings (verified:
    # a 3-line real answer+explanation string estimated at 33mm when
    # fpdf2's own line-wrapping only needed 16.5mm) — visible as growing
    # trailing whitespace at the bottom of answer-key cards, worse the
    # longer the text. Overridden here to ask fpdf2 to actually wrap the
    # text (dry_run, no drawing) and count the real resulting lines,
    # which is exact rather than approximate. Not patched upstream in
    # RevisionPDF since that file already shipped and works for its own
    # content; this override only affects AssessmentPDF's own rendering.

    def _estimate_multiline_h(
        self,
        text: str,
        w: float,
        font_size: float = 8.0
    ) -> float:
        self.set_font(FONT_REGULAR, "", font_size)
        lines = self.multi_cell(
            w, 1.0, _strip_markdown_inline(text),
            border=0, align="L",
            dry_run=True, output="LINES"
        )
        return max(1, len(lines)) * LINE_H_BODY

    # ------------------------------------------------------------------
    # Question block dispatcher
    # ------------------------------------------------------------------

    def draw_question_block(self, question: Question, display_number: int):
        """
        Render one question as a numbered block:
          [Q{display_number}]  [type]                    [difficulty badge]
          <question text>
          <type-specific answer area: lettered options or ruled lines>

        display_number is the position within the rendered document
        (1, 2, 3, ... across the whole assessment or restarted per
        chapter — caller's choice), kept separate from
        Question.question_id so renumbering for display never requires
        touching the underlying data.
        """
        question_text = _strip_markdown_inline(question.question)

        hdr_h = 9.0
        text_w = CARD_W - CARD_PAD * 2
        question_h = self._estimate_multiline_h(
            question_text, text_w, font_size=9.5
        )

        answer_area_h = self._estimate_answer_area_h(question, text_w)

        total_h = hdr_h + question_h + answer_area_h + CARD_PAD * 2 + 4.0

        self._check_page_break(total_h + CARD_GAP)
        y = self.get_y()

        self._draw_card_shell(
            MARGIN, y, CARD_W, total_h,
            COLOR_QUESTION_BG, COLOR_QUESTION_BD
        )

        # --- Header row: "Q{n}  ·  {type}" left, difficulty badge right
        self.set_font(FONT_BOLD, "B", 9.5)
        self._set_text(COLOR_TEXT_PRIMARY)
        self.set_xy(MARGIN + CARD_PAD, y + CARD_PAD - 1.0)
        self.cell(
            14.0, hdr_h, f"Q{display_number}", border=0, ln=0
        )

        self.set_font(FONT_REGULAR, "", 8.0)
        self._set_text(COLOR_TEXT_MUTED)
        self.set_xy(MARGIN + CARD_PAD + 14.0, y + CARD_PAD - 1.0)
        self.cell(
            70.0, hdr_h, question.type, border=0, ln=0
        )

        self._difficulty_badge(
            MARGIN + CARD_W - CARD_PAD - 22.0,
            y + CARD_PAD - 1.0,
            question.difficulty
        )

        # --- Question text
        text_y = y + CARD_PAD + hdr_h - 3.0
        text_bottom = self._multiline_text(
            MARGIN + CARD_PAD, text_y,
            text_w, question_text,
            font_size=9.5, bold=False
        )

        # --- Answer area
        answer_y = text_bottom + 3.0

        if question.type == "MCQ":
            self._draw_mcq_options(
                MARGIN + CARD_PAD, answer_y, text_w, question.options
            )
        elif question.type == "True/False":
            self._draw_true_false_options(
                MARGIN + CARD_PAD, answer_y, text_w
            )
        else:
            n_lines = _LINES_BY_TYPE.get(question.type, _DEFAULT_LINES)
            self._draw_lined_answer_space(
                MARGIN + CARD_PAD, answer_y, text_w, n_lines
            )

        self.set_y(y + total_h + CARD_GAP)

    # ------------------------------------------------------------------
    # MCQ options
    # ------------------------------------------------------------------

    def _draw_mcq_options(self, x: float, y: float, w: float, options: list):
        """
        Render MCQ options as lettered circles (A, B, C, D, ...),
        one per line, each with the option text beside it.
        """
        letter_r = 3.2
        letter_cx = x + letter_r
        text_x = x + letter_r * 2 + 3.5
        text_w = w - letter_r * 2 - 3.5

        cur_y = y

        for i, option_text in enumerate(options):
            letter = _MCQ_LETTERS[i] if i < len(_MCQ_LETTERS) else str(i + 1)
            line_h = max(
                self._estimate_multiline_h(option_text, text_w, font_size=8.5),
                letter_r * 2 + 1.0
            )
            # Align the circle with the FIRST line of the option's text,
            # not the vertical centre of the whole (possibly multi-line)
            # block — the text itself is drawn starting at cur_y, so
            # centring on the full block height made the circle drift
            # away from the text whenever an option wrapped to 2+ lines.
            first_line_cy = cur_y + LINE_H_BODY / 2

            self.set_fill_color(*COLOR_OPTION_CIRCLE_BG)
            self.set_draw_color(*COLOR_OPTION_CIRCLE_BG)
            self.ellipse(
                letter_cx - letter_r, first_line_cy - letter_r,
                letter_r * 2, letter_r * 2, style="F"
            )
            self.set_font(FONT_BOLD, "B", 7.5)
            self._set_text(COLOR_OPTION_CIRCLE_TEXT)
            self.set_xy(letter_cx - letter_r, first_line_cy - 2.6)
            self.cell(letter_r * 2, 5.2, letter, border=0, align="C")

            self._multiline_text(
                text_x, cur_y, text_w,
                _strip_markdown_inline(option_text),
                font_size=8.5
            )

            cur_y += line_h + 2.5

    # ------------------------------------------------------------------
    # True / False options
    # ------------------------------------------------------------------

    def _draw_true_false_options(self, x: float, y: float, w: float):
        """
        Render exactly two lettered circles, "True" and "False", side
        by side rather than stacked (only two short options, no need
        to use a full-width line each).
        """
        letter_r = 3.2
        col_w = w / 2

        for i, label in enumerate(["True", "False"]):
            col_x = x + i * col_w
            letter_cx = col_x + letter_r
            text_x = col_x + letter_r * 2 + 3.5

            self.set_fill_color(*COLOR_OPTION_CIRCLE_BG)
            self.set_draw_color(*COLOR_OPTION_CIRCLE_BG)
            self.ellipse(
                letter_cx - letter_r, y,
                letter_r * 2, letter_r * 2, style="F"
            )
            self.set_font(FONT_BOLD, "B", 7.5)
            self._set_text(COLOR_OPTION_CIRCLE_TEXT)
            self.set_xy(letter_cx - letter_r, y + 0.6)
            self.cell(
                letter_r * 2, 5.2, _MCQ_LETTERS[i], border=0, align="C"
            )

            self.set_font(FONT_REGULAR, "", 8.5)
            self._set_text(COLOR_TEXT_PRIMARY)
            self.set_xy(text_x, y + 0.6)
            self.cell(col_w - letter_r * 2 - 3.5, 5.2, label, border=0)

    # ------------------------------------------------------------------
    # Ruled answer lines (free-response types)
    # ------------------------------------------------------------------

    def _draw_lined_answer_space(self, x: float, y: float, w: float, n_lines: int):
        """Draw n_lines horizontal ruled lines for a written answer."""
        self.set_draw_color(*COLOR_RULED_LINE)
        self.set_line_width(0.2)

        for i in range(n_lines):
            line_y = y + i * RULED_LINE_GAP + RULED_LINE_GAP
            self.line(x, line_y, x + w, line_y)

    # ------------------------------------------------------------------
    # Difficulty badge
    # ------------------------------------------------------------------

    def _difficulty_badge(self, x: float, y: float, difficulty: str):
        """Small filled pill showing the difficulty label."""
        color = DIFFICULTY_COLORS.get(difficulty, COLOR_TEXT_MUTED)
        badge_w = 22.0
        badge_h = 5.5

        self.set_fill_color(*color)
        self.set_draw_color(*color)
        self.rect(
            x, y, badge_w, badge_h,
            style="F", round_corners=True, corner_radius=2.5
        )

        self.set_font(FONT_BOLD, "B", 7.0)
        self._set_text((255, 255, 255))
        self.set_xy(x, y + 0.3)
        self.cell(badge_w, badge_h - 0.3, difficulty, border=0, align="C")

    # ------------------------------------------------------------------
    # Height estimation (mirrors revision_pdf_builder's pattern of an
    # _estimate_*_h helper per card type, used for page-break decisions)
    # ------------------------------------------------------------------

    def _estimate_answer_area_h(self, question: Question, text_w: float) -> float:
        if question.type == "MCQ":
            letter_r = 3.2
            opt_text_w = text_w - letter_r * 2 - 3.5
            total = 0.0
            for opt in question.options:
                line_h = max(
                    self._estimate_multiline_h(opt, opt_text_w, font_size=8.5),
                    letter_r * 2 + 1.0
                )
                total += line_h + 2.5
            return total

        if question.type == "True/False":
            return 7.0  # single row, two columns

        n_lines = _LINES_BY_TYPE.get(question.type, _DEFAULT_LINES)
        return n_lines * RULED_LINE_GAP + 2.0

    # ------------------------------------------------------------------
    # Answer key
    # ------------------------------------------------------------------

    def add_answer_key_divider(self):
        """
        Section-level divider for the answer key, visually distinct
        from a per-chapter add_chapter_divider() bar so it's
        unmistakably a different part of the document (not "one more
        chapter") even when flipping through quickly.
        """
        self.new_content_page()

        band_h = 16.0
        self.set_fill_color(*COLOR_DEFINITION_ACC)
        self.set_draw_color(*COLOR_DEFINITION_ACC)
        self.rect(MARGIN, self.get_y(), CARD_W, band_h, style="F")

        self.set_font(FONT_BOLD, "B", 13.0)
        self._set_text((255, 255, 255))
        self.set_xy(MARGIN + CARD_PAD, self.get_y() + 3.2)
        self.cell(CARD_W - CARD_PAD * 2, band_h - 3.2, "Answer Key", border=0, ln=1)

        self.set_y(self.get_y() + band_h - 3.2 + CARD_GAP + 2.0)

        self.set_font(FONT_REGULAR, "", 8.5)
        self._set_text(COLOR_TEXT_SECONDARY)
        self.set_x(MARGIN)
        self.multi_cell(
            CARD_W, 5.0,
            "Answers and explanations, grouped by chapter and in the "
            "same order as the questions.",
            border=0, align="L"
        )
        self.set_y(self.get_y() + CARD_GAP)

    def draw_answer_key_entry(self, question: Question, display_number: int):
        """
        One compact answer-key row:
            Q{n}  [concepts tag(s)]
            Answer: ...
            Why: ...

        Deliberately denser than draw_question_block — this section is
        a reference list, not a worksheet, and can get long for a
        many-chapter assessment.
        """
        answer_text = _strip_markdown_inline(question.answer)
        explanation_text = _strip_markdown_inline(question.explanation)

        text_w = CARD_W - CARD_PAD * 2

        answer_h = self._estimate_multiline_h(
            f"Answer: {answer_text}", text_w, font_size=8.5
        )
        explanation_h = self._estimate_multiline_h(
            f"Why: {explanation_text}", text_w, font_size=8.0
        )

        hdr_h = 6.0
        total_h = hdr_h + answer_h + explanation_h + CARD_PAD * 1.5 + 2.0

        self._check_page_break(total_h + CARD_GAP * 0.6)
        y = self.get_y()

        self._draw_card_shell(
            MARGIN, y, CARD_W, total_h,
            COLOR_TEXT_CARD_BG, COLOR_TEXT_CARD_BD
        )

        # Header: Q{n} + concept tags, muted
        self.set_font(FONT_BOLD, "B", 8.5)
        self._set_text(COLOR_TEXT_PRIMARY)
        self.set_xy(MARGIN + CARD_PAD, y + CARD_PAD * 0.6)
        self.cell(16.0, hdr_h, f"Q{display_number}", border=0, ln=0)

        if question.concepts:
            self.set_font(FONT_REGULAR, "", 7.5)
            self._set_text(COLOR_TEXT_MUTED)
            self.set_xy(MARGIN + CARD_PAD + 16.0, y + CARD_PAD * 0.6)
            self.cell(
                text_w - 16.0, hdr_h,
                " · ".join(question.concepts), border=0, ln=0
            )

        # Answer
        answer_y = y + CARD_PAD * 0.6 + hdr_h
        answer_bottom = self._multiline_text(
            MARGIN + CARD_PAD, answer_y, text_w,
            f"Answer: {answer_text}",
            font_size=8.5, bold=False
        )

        # Explanation, muted
        self._multiline_text(
            MARGIN + CARD_PAD, answer_bottom + 1.0, text_w,
            f"Why: {explanation_text}",
            font_size=8.0, color=COLOR_TEXT_SECONDARY
        )

        self.set_y(y + total_h + CARD_GAP * 0.6)


# ---------------------------------------------------------------------------
# Chapter title lookup
# ---------------------------------------------------------------------------

def load_chapter_titles_from_outline(outline_path: str | Path) -> dict[int, str]:
    """
    Read outputs/notes/lecture_outline.json and return {chapter_id: title}.

    This is the same file assessment_generator.main() already reads for
    lecture_title — Question/Assessment never carry a chapter title
    themselves (only chapter_id), so this is the actual source of
    truth for what to print on each chapter divider.

    Returns an empty dict (rather than raising) if the file doesn't
    exist or doesn't parse as expected — callers fall back to a bare
    "Chapter {id}" label per chapter in that case, so a missing or
    malformed outline degrades the dividers rather than failing the
    whole PDF build.
    """
    outline_path = Path(outline_path)

    if not outline_path.exists():
        return {}

    try:
        with open(outline_path, "r", encoding="utf-8") as f:
            outline = json.load(f)

        return {
            chapter["chapter_id"]: chapter["title"]
            for chapter in outline.get("chapters", [])
            if "chapter_id" in chapter and "title" in chapter
        }
    except (json.JSONDecodeError, KeyError, TypeError):
        return {}


def _default_outline_path(assessment_path: Path) -> Path:
    """
    Best-guess location of lecture_outline.json given assessment.json's
    path, based on the real output layout:

        outputs/
            notes/
                lecture_outline.json
            assessment/
                assessment.json

    i.e. a sibling "notes" directory next to assessment.json's parent.
    Just a default guess for convenience — pass chapter_titles or
    outline_path explicitly to build_assessment_pdf() if the real
    layout differs.
    """
    return assessment_path.parent.parent / "notes" / "lecture_outline.json"


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

def build_assessment_pdf(
    assessment_path: str | Path,
    output_path: str | Path,
    chapter_titles: dict[int, str] | None = None,
    outline_path: str | Path | None = None,
):
    """
    Build an assessment PDF from assessment.json.

    Layout:
        - Cover page (lecture title, chapter/question counts, date)
        - Per chapter: chapter divider, then every question in that
          chapter as a numbered question block (no answers visible)
        - Answer Key section: divider, then every chapter's questions
          again, this time as compact answer + explanation entries

    Question numbering is restarted per chapter for both the question
    pages and the answer key (Q1, Q2, ... within each chapter) so a
    student working chapter-by-chapter has a clean Q1 to start from
    each time, and the answer key's numbering matches what's printed
    above each question on the worksheet pages.

    Args:
        assessment_path : path to assessment.json
        output_path      : path to write the .pdf
        chapter_titles   : optional {chapter_id: title} map, used for
            chapter divider headings. Takes priority over outline_path
            if both are given. If omitted entirely, chapter titles are
            loaded automatically from lecture_outline.json (see
            outline_path below) — pass an explicit empty dict ({}) to
            opt out and force bare "Chapter {id}" labels instead.
        outline_path     : path to lecture_outline.json to load chapter
            titles from, used only when chapter_titles is not given.
            Defaults to a sibling "notes/lecture_outline.json" next to
            assessment_path's parent directory, matching the real
            outputs/notes/ + outputs/assessment/ layout. If the file
            is missing or doesn't parse as expected, this silently
            falls back to bare "Chapter {id}" labels rather than
            failing the build.
    """

    assessment_path = Path(assessment_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if chapter_titles is None:
        resolved_outline_path = (
            Path(outline_path)
            if outline_path is not None
            else _default_outline_path(assessment_path)
        )
        chapter_titles = load_chapter_titles_from_outline(resolved_outline_path)

    raw = assessment_path.read_text(encoding="utf-8")
    assessment = Assessment.model_validate_json(raw)

    pdf = AssessmentPDF()
    pdf.setup()
    pdf.add_cover_page(assessment.metadata, subtitle="Assessment")

    chapter_ids = sorted({q.chapter_id for q in assessment.questions})

    def divider_label(chapter_id: int, suffix: str = "") -> str:
        title = chapter_titles.get(chapter_id, f"Chapter {chapter_id}")
        return f"{title}{suffix}"

    pdf.new_content_page()

    for chapter_id in chapter_ids:
        chapter_questions = assessment.questions_for_chapter(chapter_id)

        pdf.add_chapter_divider(divider_label(chapter_id))

        for display_number, question in enumerate(chapter_questions, start=1):
            pdf.draw_question_block(question, display_number)

    pdf.add_answer_key_divider()

    for chapter_id in chapter_ids:
        chapter_questions = assessment.questions_for_chapter(chapter_id)

        pdf.add_chapter_divider(divider_label(chapter_id, " — Answers"))

        for display_number, question in enumerate(chapter_questions, start=1):
            pdf.draw_answer_key_entry(question, display_number)

    pdf.output(str(output_path))