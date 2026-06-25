"""
revision_pdf_builder.py

├── Config & Theme
├── RevisionPDF         (FPDF subclass)
│   ├── setup()
│   ├── new_content_page()
│   ├── add_cover_page()
│   ├── add_chapter_divider()
│   ├── _card_header()
│   ├── _check_page_break()
│   ├── draw_definition_card()
│   ├── draw_bullets_card()
│   ├── draw_steps_card()
│   ├── draw_table_card()
│   ├── draw_tips_card()
│   ├── draw_errors_card()
│   ├── draw_summary_card()
│   ├── draw_formula_card()
│   ├── draw_text_card()
│   └── draw_block()
│
└── Entry Point
    └── build_revision_pdf()
"""


import re
from pathlib import Path
from fpdf import FPDF
from revision_notes.revision_parser import (
    Block,
    TableRow,
    parse_revision_markdown,
)


# ---------------------------------------------------------------------------
# Config & Theme
# ---------------------------------------------------------------------------

PAGE_W       = 210          # A4 width  mm
PAGE_H       = 297          # A4 height mm
MARGIN       = 14           # left/right/top margin mm
CARD_W       = PAGE_W - MARGIN * 2
CARD_PAD     = 5            # inner padding inside cards mm
CARD_GAP     = 4            # vertical gap between cards mm
CARD_RADIUS  = 3            # corner rounding mm
LINE_H_BODY  = 5.5          # line height for body text mm
LINE_H_TITLE = 6.5          # line height for card titles mm

# Fonts — DejaVu Sans (Unicode, covers all revision content)
FONT_REGULAR  = "DejaVu"
FONT_BOLD     = "DejaVu"
FONT_MONO     = "DejaVuMono"

DEJAVU_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
DEJAVU_BOLD    = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
DEJAVU_MONO    = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"

# Palette — (R, G, B)
COLOR_PAGE_BG        = (250, 250, 248)   # warm off-white page
COLOR_TEXT_PRIMARY   = (30,  30,  28)
COLOR_TEXT_SECONDARY = (90,  88,  84)
COLOR_TEXT_MUTED     = (140, 138, 132)

COLOR_DIVIDER_BG     = (30,  30,  28)    # dark chapter bar
COLOR_DIVIDER_TEXT   = (255, 255, 255)

COLOR_DEFINITION_BG  = (240, 238, 255)   # soft purple
COLOR_DEFINITION_BD  = (180, 174, 230)
COLOR_DEFINITION_ACC = (100,  88, 196)   # left accent bar

COLOR_BULLETS_BG     = (245, 245, 243)
COLOR_BULLETS_BD     = (210, 208, 202)
COLOR_BULLETS_DOT    = (100,  88, 196)

COLOR_STEPS_BG       = (240, 248, 255)   # soft blue
COLOR_STEPS_BD       = (174, 210, 240)
COLOR_STEPS_NUM_BG   = ( 55, 130, 200)
COLOR_STEPS_NUM_TEXT = (255, 255, 255)

COLOR_TABLE_BG       = (245, 245, 243)
COLOR_TABLE_BD       = (200, 198, 192)
COLOR_TABLE_HDR_BG   = ( 30,  30,  28)
COLOR_TABLE_HDR_TEXT = (255, 255, 255)
COLOR_TABLE_ROW_ALT  = (235, 234, 230)

COLOR_TIPS_BG        = (255, 251, 235)   # warm amber
COLOR_TIPS_BD        = (240, 196, 100)
COLOR_TIPS_ACC       = (200, 140,  20)

COLOR_ERRORS_BG      = (255, 240, 240)   # soft red
COLOR_ERRORS_BD      = (240, 170, 170)
COLOR_ERRORS_ACC     = (190,  60,  60)

COLOR_SUMMARY_BG     = (236, 252, 240)   # soft green
COLOR_SUMMARY_BD     = (160, 220, 175)
COLOR_SUMMARY_ACC    = ( 40, 150,  80)

COLOR_FORMULA_BG     = (255, 255, 255)
COLOR_FORMULA_BD     = (180, 174, 230)
COLOR_FORMULA_ACC    = (100,  88, 196)

COLOR_TEXT_CARD_BG   = (245, 245, 243)
COLOR_TEXT_CARD_BD   = (210, 208, 202)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _latex_to_plain(expr: str) -> str:
    """
    Convert a LaTeX math expression to readable plain text.
    Handles the most common patterns found in revision notes.
    """
    # Strip $ delimiters
    expr = re.sub(r"\$\$(.+?)\$\$", r"\1", expr, flags=re.DOTALL)
    expr = re.sub(r"\$(.+?)\$", r"\1", expr)

    # Fractions: \frac{a}{b} -> a/b
    expr = re.sub(r"\\frac\{([^}]+)\}\{([^}]+)\}", r"\1/\2", expr)

    # Subscripts/superscripts with braces
    expr = re.sub(r"_\{([^}]+)\}", r"_\1", expr)
    expr = re.sub(r"\^\{([^}]+)\}", r"^\1", expr)

    replacements = [
        (r"\\log",                   "log"),
        (r"\\ln",                    "ln"),
        (r"\\sqrt",                  "sqrt"),
        (r"\\sum",                   "sum"),
        (r"\\prod",                  "prod"),
        (r"\\min",                   "min"),
        (r"\\max",                   "max"),
        (r"\\gcd",                   "gcd"),
        (r"\\lcm",                   "lcm"),
        (r"\\lfloor",                "floor("),
        (r"\\rfloor",                ")"),
        (r"\\lceil",                 "ceil("),
        (r"\\rceil",                 ")"),
        (r"\\infty",                 "inf"),
        (r"\\emptyset",              "{}"),
        (r"\\in",                    "in"),
        (r"\\subseteq",              "<="),
        (r"\\cap",                   "n"),
        (r"\\cup",                   "u"),
        (r"\\rightarrow",            "->"),
        (r"\\leftarrow",             "<-"),
        (r"\\Rightarrow",            "=>"),
        (r"\\le",                    "<="),
        (r"\\ge",                    ">="),
        (r"\\neq",                   "!="),
        (r"\\cdot",                  "*"),
        (r"\\times",                 "x"),
        (r"\\text\{([^}]+)\}",     r"\1"),
        (r"\\mathrm\{([^}]+)\}",   r"\1"),
        (r"\\mathbf\{([^}]+)\}",   r"\1"),
        (r"\\[a-zA-Z]+",             ""),
        (r"[{}]",                      ""),
    ]

    for pattern, replacement in replacements:
        expr = re.sub(pattern, replacement, expr)

    return expr.strip()


def _strip_markdown_inline(text: str) -> str:
    """
    Remove inline markdown formatting for plain PDF rendering.
    Converts LaTeX math to readable plain text.
    Strips: **bold**, *italic*, `code`
    """
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*",       r"\1", text)
    text = re.sub(r"`(.+?)`",           r"\1", text)

    # Convert math expressions
    text = re.sub(
        r"\$\$(.+?)\$\$",
        lambda m: _latex_to_plain(m.group(0)),
        text, flags=re.DOTALL
    )
    text = re.sub(
        r"\$(.+?)\$",
        lambda m: _latex_to_plain(m.group(0)),
        text
    )

    return text.strip()


def _strip_bullet_prefix(line: str) -> str:
    """Remove leading bullet markers from a line."""
    return re.sub(r"^[-*•+]\s+", "", line).strip()


def _strip_number_prefix(line: str) -> str:
    """Remove leading number markers from a line."""
    return re.sub(
        r"^(\d+[\.\)]|step\s+\d+:?)\s*",
        "", line, flags=re.IGNORECASE
    ).strip()


# ---------------------------------------------------------------------------
# RevisionPDF
# ---------------------------------------------------------------------------

class RevisionPDF(FPDF):

    def setup(self):
        """
        Initialise page settings and register Unicode fonts.

        Does NOT add the first page — callers decide whether
        that first page is a cover page or the first chapter,
        and call new_content_page() or add_cover_page() themselves.
        """
        self.add_font("DejaVu",     "",  DEJAVU_REGULAR, uni=True)
        self.add_font("DejaVu",     "B", DEJAVU_BOLD,    uni=True)
        self.add_font("DejaVuMono", "",  DEJAVU_MONO,    uni=True)
        self.set_margins(MARGIN, MARGIN, MARGIN)
        self.set_auto_page_break(False, margin=MARGIN)

    def new_content_page(self):
        """Start a fresh page with the standard page background."""
        self.add_page()
        self._fill_page_bg()
        self.set_y(MARGIN)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fill_page_bg(self):
        """Paint the page background colour."""
        self.set_fill_color(*COLOR_PAGE_BG)
        self.rect(0, 0, PAGE_W, PAGE_H, style="F")

    def _set_fill(self, rgb):
        self.set_fill_color(*rgb)

    def _set_draw(self, rgb):
        self.set_draw_color(*rgb)

    def _set_text(self, rgb):
        self.set_text_color(*rgb)

    # ------------------------------------------------------------------
    # Cover Page
    # ------------------------------------------------------------------

    def add_cover_page(self, metadata, subtitle: str = "Revision Notes"):
        """
        Render a full cover page before the chapter loop starts.

        Args:
            metadata: a RevisionMetadata instance (or any object /
                      mapping exposing lecture_title, total_chapters,
                      estimated_read_time and generated_at).
            subtitle: small label under the NorAI wordmark. Defaults
                      to "Revision Notes"; subclasses for other
                      document types (e.g. AssessmentPDF) pass their
                      own label and override _cover_strip_items() to
                      change what the bottom metadata strip shows.

        Layout (top to bottom):
            - Dark band with the NorAI wordmark
            - A row of small accent dots (echoes the card colour system)
            - Lecture title, large, vertically centred in the
              remaining space
            - Thin purple accent rule
            - Metadata strip: chapters · read time · generated date
        """
        lecture_title = self._meta_get(metadata, "lecture_title", "")

        self.new_content_page()

        # --- Top wordmark band -------------------------------------------------
        band_h = 46.0
        self.set_fill_color(*COLOR_DIVIDER_BG)
        self.set_draw_color(*COLOR_DIVIDER_BG)
        self.rect(0, 0, PAGE_W, band_h, style="F")

        self.set_font(FONT_BOLD, "B", 23.0)
        self._set_text(COLOR_DIVIDER_TEXT)
        self.set_xy(MARGIN, band_h / 2 - 9.0)
        self.cell(CARD_W, 14.0, "NorAI", border=0, ln=0)

        self.set_font(FONT_REGULAR, "", 9.0)
        self._set_text((190, 188, 196))  # muted on dark
        self.set_xy(MARGIN, band_h / 2 + 4.0)
        self.cell(
            CARD_W, 6.0,
            subtitle, border=0, ln=0
        )

        # --- Accent dot motif, echoing the card-type colour system -------------
        dot_colors = [
            COLOR_DEFINITION_ACC, COLOR_STEPS_NUM_BG,
            COLOR_TIPS_ACC, COLOR_ERRORS_ACC, COLOR_SUMMARY_ACC,
        ]
        dot_r   = 1.6
        dot_gap = 7.0
        row_w   = (len(dot_colors) - 1) * dot_gap
        dots_y  = band_h + 30.0
        start_x = PAGE_W / 2 - row_w / 2
        for i, color in enumerate(dot_colors):
            cx = start_x + i * dot_gap
            self.set_fill_color(*color)
            self.set_draw_color(*color)
            self.ellipse(
                cx - dot_r, dots_y - dot_r,
                dot_r * 2, dot_r * 2, style="F"
            )

        # --- Lecture title, vertically centred in the remaining space ----------
        footer_zone_h = 40.0
        available_top    = dots_y + 14.0
        available_bottom = PAGE_H - footer_zone_h

        self.set_font(FONT_BOLD, "B", 20.0)
        title_line_h = 9.5
        title_text = _strip_markdown_inline(lecture_title)
        n_lines = self._count_multicell_lines(
            title_text, CARD_W, font_size=20.0
        )
        title_block_h = n_lines * title_line_h

        title_top = (
            available_top
            + (available_bottom - available_top - title_block_h) / 2
        )
        title_top = max(title_top, available_top)

        self._set_text(COLOR_TEXT_PRIMARY)
        self.set_xy(MARGIN, title_top)
        self.multi_cell(
            CARD_W, title_line_h,
            title_text,
            border=0, align="C"
        )

        # --- Accent rule beneath the title --------------------------------------
        rule_y = self.get_y() + 9.0
        rule_w = 36.0
        self.set_fill_color(*COLOR_DEFINITION_ACC)
        self.set_draw_color(*COLOR_DEFINITION_ACC)
        self.rect(
            PAGE_W / 2 - rule_w / 2, rule_y,
            rule_w, 1.2, style="F"
        )

        # --- Metadata strip, anchored near the bottom of the page ---------------
        strip_items = self._cover_strip_items(metadata)

        if strip_items:
            strip_y = PAGE_H - MARGIN - 18.0
            self.set_font(FONT_REGULAR, "", 9.0)
            self._set_text(COLOR_TEXT_SECONDARY)
            self.set_xy(MARGIN, strip_y)
            separator = "      ·      "
            self.cell(
                CARD_W, 6.0,
                separator.join(strip_items),
                border=0, align="C"
            )

    def _cover_strip_items(self, metadata) -> list[str]:
        """
        Build the list of short strings shown in the cover page's
        bottom metadata strip. Split out from add_cover_page() so
        subclasses (e.g. AssessmentPDF) can override just this piece
        — different document types have different metadata fields
        (RevisionMetadata.estimated_read_time vs
        AssessmentMetadata.estimated_time, plus assessments wanting a
        question count) without needing to override or duplicate the
        entire cover page layout.
        """
        total_chapters      = self._meta_get(metadata, "total_chapters", None)
        estimated_read_time = self._meta_get(metadata, "estimated_read_time", None)
        generated_at        = self._meta_get(metadata, "generated_at", "")

        strip_items = []
        if total_chapters is not None:
            label = "Chapter" if total_chapters == 1 else "Chapters"
            strip_items.append(f"{total_chapters} {label}")
        if estimated_read_time is not None:
            strip_items.append(f"{estimated_read_time} min read")
        date_str = self._format_generated_at(generated_at)
        if date_str:
            strip_items.append(date_str)

        return strip_items

    def _count_multicell_lines(
        self, text: str, w: float, font_size: float = 8.0
    ) -> int:
        """
        Count how many lines a multi_cell will wrap to, using fpdf2's
        own line-splitting so the estimate matches actual rendering
        (used to vertically centre the cover title block).
        """
        self.set_font(FONT_BOLD, "B", font_size)
        lines = self.multi_cell(
            w, 1.0, text, border=0, align="C",
            dry_run=True, output="LINES"
        )
        return max(1, len(lines))

    @staticmethod
    def _meta_get(metadata, field: str, default=None):
        """Read a field off a pydantic model, dict, or plain object."""
        if metadata is None:
            return default
        if isinstance(metadata, dict):
            return metadata.get(field, default)
        return getattr(metadata, field, default)

    @staticmethod
    def _format_generated_at(generated_at: str) -> str:
        """
        Format an ISO timestamp (e.g. RevisionMetadata.generated_at)
        into a short human-readable date, e.g. '25 June 2026'.
        Falls back to the raw string if parsing fails.
        """
        if not generated_at:
            return ""
        try:
            from datetime import datetime
            cleaned = generated_at.replace("Z", "+00:00")
            dt = datetime.fromisoformat(cleaned)
            return dt.strftime("%-d %B %Y")
        except (ValueError, TypeError):
            return generated_at.split("T")[0] if "T" in generated_at else generated_at

    def _check_page_break(self, needed_h: float):
        """
        If remaining space on page < needed_h,
        start a new page.
        """
        remaining = PAGE_H - MARGIN - self.get_y()
        if remaining < needed_h:
            self.new_content_page()

    def _card_header(
        self,
        x: float, y: float,
        title: str,
        bg: tuple, text_color: tuple,
        font_size: float = 8.5
    ):
        """
        Draw a card title bar at (x, y) spanning CARD_W.
        Returns the y position after the header.
        """
        hdr_h = 7.0
        self._set_fill(bg)
        self._set_draw(bg)
        self.set_xy(x, y)
        self.set_font(FONT_BOLD, "B", font_size)
        self._set_text(text_color)
        self.set_fill_color(*bg)
        self.set_draw_color(*bg)
        self.rect(x, y, CARD_W, hdr_h, style="F")
        self.set_xy(x + CARD_PAD, y + 1.2)
        self.cell(CARD_W - CARD_PAD * 2, hdr_h - 1.2,
                  _strip_markdown_inline(title),
                  border=0, ln=0)
        return y + hdr_h

    def _draw_card_shell(
        self,
        x: float, y: float,
        w: float, h: float,
        bg: tuple, border: tuple
    ):
        """Draw the card background rect with border."""
        self._set_fill(bg)
        self._set_draw(border)
        self.set_line_width(0.25)
        self.rect(
            x, y, w, h,
            style="FD",
            round_corners=True,
            corner_radius=CARD_RADIUS
        )

    def _draw_left_accent(
        self,
        x: float, y: float,
        h: float,
        color: tuple,
        width: float = 2.5
    ):
        """Draw a vertical left accent bar on a card."""
        self.set_fill_color(*color)
        self.set_draw_color(*color)
        self.set_line_width(0)
        self.rect(x, y, width, h, style="F")

    def _multiline_text(
        self,
        x: float, y: float,
        w: float,
        text: str,
        font_size: float = 8.0,
        color: tuple = COLOR_TEXT_PRIMARY,
        bold: bool = False
    ) -> float:
        """
        Write multi-line text inside width w.
        Returns new y after text.
        """
        self.set_font(
            FONT_BOLD if bold else FONT_REGULAR,
            "B" if bold else "",
            font_size
        )
        self._set_text(color)
        self.set_xy(x, y)
        self.multi_cell(
            w, LINE_H_BODY,
            _strip_markdown_inline(text),
            border=0, align="L"
        )
        return self.get_y()

    def _estimate_multiline_h(
        self,
        text: str,
        w: float,
        font_size: float = 8.0
    ) -> float:
        """
        Rough estimate of height a multi_cell will take.
        Used for page-break decisions.
        """
        chars_per_line = max(1, int(w / (font_size * 0.45)))
        words = _strip_markdown_inline(text).split()
        lines = 1
        current = 0
        for word in words:
            if current + len(word) + 1 > chars_per_line:
                lines += 1
                current = len(word)
            else:
                current += len(word) + 1
        return lines * LINE_H_BODY

    # ------------------------------------------------------------------
    # Chapter Divider
    # ------------------------------------------------------------------

    def add_chapter_divider(self, title: str):
        """
        Full-width dark bar with chapter title.
        Always starts on a fresh vertical position
        with a small gap above.
        """
        gap_above = 6.0
        bar_h     = 11.0

        self._check_page_break(
            gap_above + bar_h + CARD_GAP
        )

        y = self.get_y() + gap_above

        self.set_fill_color(*COLOR_DIVIDER_BG)
        self.set_draw_color(*COLOR_DIVIDER_BG)
        self.rect(MARGIN, y, CARD_W, bar_h, style="F")

        self.set_font(FONT_BOLD, "B", 10.5)
        self._set_text(COLOR_DIVIDER_TEXT)
        self.set_xy(MARGIN + CARD_PAD, y + 1.8)
        self.cell(
            CARD_W - CARD_PAD * 2,
            bar_h - 1.8,
            _strip_markdown_inline(title),
            border=0, ln=1
        )

        self.set_y(y + bar_h + CARD_GAP)

    # ------------------------------------------------------------------
    # draw_block dispatcher
    # ------------------------------------------------------------------

    def draw_block(self, block: Block):
        """Route a Block to its renderer."""
        dispatch = {
            "definition": self.draw_definition_card,
            "bullets":    self.draw_bullets_card,
            "steps":      self.draw_steps_card,
            "table":      self.draw_table_card,
            "tips":       self.draw_tips_card,
            "errors":     self.draw_errors_card,
            "summary":    self.draw_summary_card,
            "formula":    self.draw_formula_card,
            "text":       self.draw_text_card,
        }
        renderer = dispatch.get(
            block.type,
            self.draw_text_card
        )
        renderer(block)

    # ------------------------------------------------------------------
    # Card renderers
    # ------------------------------------------------------------------

    def draw_definition_card(self, block: Block):
        """
        Short dense prose block.
        Left purple accent bar, light purple background.
        """
        accent_w = 2.5
        inner_x  = MARGIN + accent_w + CARD_PAD
        inner_w  = CARD_W - accent_w - CARD_PAD * 2

        lines = [
            _strip_markdown_inline(l)
            for l in block.content
            if isinstance(l, str) and l.strip()
        ]
        text = " ".join(lines)

        body_h = self._estimate_multiline_h(text, inner_w)
        hdr_h  = 7.0
        total_h = hdr_h + body_h + CARD_PAD * 2

        self._check_page_break(total_h + CARD_GAP)
        y = self.get_y()

        self._draw_card_shell(
            MARGIN, y, CARD_W, total_h,
            COLOR_DEFINITION_BG, COLOR_DEFINITION_BD
        )
        self._draw_left_accent(
            MARGIN, y, total_h,
            COLOR_DEFINITION_ACC, accent_w
        )

        # Header
        body_y = self._card_header(
            MARGIN, y, block.title,
            COLOR_DEFINITION_ACC,
            (255, 255, 255),
            font_size=8.5
        )

        # Body
        self._multiline_text(
            inner_x, body_y + CARD_PAD,
            inner_w, text,
            font_size=8.0
        )

        self.set_y(y + total_h + CARD_GAP)

    def draw_bullets_card(self, block: Block):
        """
        Bullet list block.
        Neutral background, purple dot per bullet.
        """
        dot_r   = 1.0
        dot_x   = MARGIN + CARD_PAD + dot_r
        text_x  = MARGIN + CARD_PAD + dot_r * 2 + 2.5
        text_w  = CARD_W - CARD_PAD * 2 - dot_r * 2 - 2.5

        lines = [
            _strip_bullet_prefix(
                _strip_markdown_inline(l)
            )
            for l in block.content
            if isinstance(l, str) and l.strip()
            and not l.strip().startswith("#")
        ]

        # Estimate total height
        hdr_h   = 7.0
        body_h  = sum(
            self._estimate_multiline_h(l, text_w)
            for l in lines
        ) + len(lines) * 1.5
        total_h = hdr_h + body_h + CARD_PAD * 2

        self._check_page_break(total_h + CARD_GAP)
        y = self.get_y()

        self._draw_card_shell(
            MARGIN, y, CARD_W, total_h,
            COLOR_BULLETS_BG, COLOR_BULLETS_BD
        )

        body_y = self._card_header(
            MARGIN, y, block.title,
            COLOR_BULLETS_BD,
            COLOR_TEXT_PRIMARY,
            font_size=8.5
        )

        cur_y = body_y + CARD_PAD

        for line in lines:
            line_h = self._estimate_multiline_h(
                line, text_w
            )
            # dot — vertically centred on first line
            self.set_fill_color(*COLOR_BULLETS_DOT)
            self.ellipse(
                dot_x - dot_r,
                cur_y + LINE_H_BODY * 0.35,
                dot_r * 2, dot_r * 2,
                style="F"
            )
            self._multiline_text(
                text_x, cur_y, text_w, line,
                font_size=8.0
            )
            cur_y += line_h + 1.5

        self.set_y(y + total_h + CARD_GAP)

    def draw_steps_card(self, block: Block):
        """
        Numbered steps block.
        Blue background, filled circle step numbers.
        """
        num_r   = 3.5        # circle radius mm
        num_cx  = MARGIN + CARD_PAD + num_r
        text_x  = MARGIN + CARD_PAD + num_r * 2 + 3.0
        text_w  = CARD_W - CARD_PAD * 2 - num_r * 2 - 3.0

        lines = [
            _strip_number_prefix(
                _strip_markdown_inline(l)
            )
            for l in block.content
            if isinstance(l, str) and l.strip()
            and re.match(
                r"^(\d+[\.\)]|step\s+\d+:?|-|\*|•)",
                l.strip(), re.IGNORECASE
            )
        ]

        if not lines:
            lines = [
                _strip_markdown_inline(l)
                for l in block.content
                if isinstance(l, str) and l.strip()
            ]

        hdr_h   = 7.0
        body_h  = sum(
            max(
                self._estimate_multiline_h(l, text_w),
                num_r * 2
            ) + 3.0
            for l in lines
        )
        total_h = hdr_h + body_h + CARD_PAD * 2

        self._check_page_break(total_h + CARD_GAP)
        y = self.get_y()

        self._draw_card_shell(
            MARGIN, y, CARD_W, total_h,
            COLOR_STEPS_BG, COLOR_STEPS_BD
        )

        body_y = self._card_header(
            MARGIN, y, block.title,
            COLOR_STEPS_BD,
            COLOR_TEXT_PRIMARY,
            font_size=8.5
        )

        cur_y = body_y + CARD_PAD

        for i, line in enumerate(lines, start=1):
            line_h = max(
                self._estimate_multiline_h(line, text_w),
                num_r * 2
            )
            cy = cur_y + line_h / 2

            # Number circle
            self.set_fill_color(*COLOR_STEPS_NUM_BG)
            self.set_draw_color(*COLOR_STEPS_NUM_BG)
            self.ellipse(
                num_cx - num_r, cy - num_r,
                num_r * 2, num_r * 2,
                style="F"
            )
            self.set_font(FONT_BOLD, "B", 7.0)
            self._set_text(COLOR_STEPS_NUM_TEXT)
            self.set_xy(num_cx - num_r, cy - 2.8)
            self.cell(
                num_r * 2, 5.5,
                str(i), border=0,
                align="C"
            )

            # Step text
            self._multiline_text(
                text_x, cur_y, text_w, line,
                font_size=8.0
            )
            cur_y += line_h + 3.0

        self.set_y(y + total_h + CARD_GAP)

    def draw_table_card(self, block: Block):
        """
        Markdown table block.
        Dark header row, alternating body rows.
        Columns sized equally across CARD_W.
        """
        rows = [
            r for r in block.content
            if isinstance(r, TableRow)
        ]

        if not rows:
            self.draw_text_card(block)
            return

        n_cols  = max(len(r.cells) for r in rows)
        col_w   = (CARD_W - CARD_PAD * 2) / max(n_cols, 1)
        row_h   = 6.5
        hdr_h   = 7.0
        total_h = hdr_h + len(rows) * row_h + CARD_PAD

        self._check_page_break(total_h + CARD_GAP)
        y = self.get_y()

        self._draw_card_shell(
            MARGIN, y, CARD_W, total_h,
            COLOR_TABLE_BG, COLOR_TABLE_BD
        )

        body_y = self._card_header(
            MARGIN, y, block.title,
            COLOR_TABLE_BD,
            COLOR_TEXT_PRIMARY,
            font_size=8.5
        )

        cur_y = body_y
        alt   = False

        for row in rows:

            if row.is_header:
                self.set_fill_color(*COLOR_TABLE_HDR_BG)
                self.set_draw_color(*COLOR_TABLE_HDR_BG)
                self.rect(
                    MARGIN, cur_y,
                    CARD_W, row_h, style="F"
                )
                self.set_font(FONT_BOLD, "B", 7.5)
                self._set_text(COLOR_TABLE_HDR_TEXT)

            else:
                fill = (
                    COLOR_TABLE_ROW_ALT
                    if alt else COLOR_TABLE_BG
                )
                self.set_fill_color(*fill)
                self.set_draw_color(*fill)
                self.rect(
                    MARGIN, cur_y,
                    CARD_W, row_h, style="F"
                )
                self.set_font(FONT_REGULAR, "", 7.5)
                self._set_text(COLOR_TEXT_PRIMARY)
                alt = not alt

            # Draw cells
            for ci, cell_text in enumerate(row.cells[:n_cols]):
                cx = MARGIN + CARD_PAD + ci * col_w
                self.set_xy(cx, cur_y + 1.0)
                self.cell(
                    col_w - 1.0, row_h - 1.0,
                    _strip_markdown_inline(cell_text),
                    border=0, align="L"
                )

            # Thin row separator
            self.set_draw_color(*COLOR_TABLE_BD)
            self.set_line_width(0.15)
            self.line(
                MARGIN, cur_y + row_h,
                MARGIN + CARD_W, cur_y + row_h
            )

            cur_y += row_h

        self.set_y(y + total_h + CARD_GAP)

    def _draw_accent_bullets_card(
        self,
        block: Block,
        bg: tuple,
        border: tuple,
        accent: tuple,
        label: str
    ):
        """
        Shared renderer for tips / errors / summary.
        Left accent bar, small label badge, bullet lines.
        """
        accent_w = 2.5
        inner_x  = MARGIN + accent_w + CARD_PAD
        inner_w  = CARD_W - accent_w - CARD_PAD * 2

        lines = [
            _strip_bullet_prefix(
                _strip_markdown_inline(l)
            )
            for l in block.content
            if isinstance(l, str) and l.strip()
            and not l.strip().startswith("#")
        ]

        hdr_h   = 7.0
        body_h  = sum(
            self._estimate_multiline_h(l, inner_w)
            for l in lines
        ) + len(lines) * 2.0
        total_h = hdr_h + body_h + CARD_PAD * 2

        self._check_page_break(total_h + CARD_GAP)
        y = self.get_y()

        self._draw_card_shell(
            MARGIN, y, CARD_W, total_h,
            bg, border
        )
        self._draw_left_accent(
            MARGIN, y, total_h, accent, accent_w
        )

        body_y = self._card_header(
            MARGIN, y, block.title,
            accent, (255, 255, 255),
            font_size=8.5
        )

        cur_y = body_y + CARD_PAD

        for line in lines:
            line_h = self._estimate_multiline_h(
                line, inner_w
            )
            # Small dash bullet
            self.set_font(FONT_REGULAR, "", 8.0)
            self._set_text(accent)
            self.set_xy(inner_x, cur_y)
            self.cell(4.0, LINE_H_BODY, "-", border=0)
            self._multiline_text(
                inner_x + 4.0, cur_y,
                inner_w - 4.0, line,
                font_size=8.0
            )
            cur_y += line_h + 2.0

        self.set_y(y + total_h + CARD_GAP)

    def draw_tips_card(self, block: Block):
        self._draw_accent_bullets_card(
            block,
            COLOR_TIPS_BG, COLOR_TIPS_BD,
            COLOR_TIPS_ACC, "Tip"
        )

    def draw_errors_card(self, block: Block):
        self._draw_accent_bullets_card(
            block,
            COLOR_ERRORS_BG, COLOR_ERRORS_BD,
            COLOR_ERRORS_ACC, "Watch out"
        )

    def draw_summary_card(self, block: Block):
        self._draw_accent_bullets_card(
            block,
            COLOR_SUMMARY_BG, COLOR_SUMMARY_BD,
            COLOR_SUMMARY_ACC, "Summary"
        )

    def draw_formula_card(self, block: Block):
        """
        Formula / equation / theorem block.
        White background, purple accent, monospace body.
        Each line rendered individually for spacing.
        """
        accent_w = 2.5
        inner_x  = MARGIN + accent_w + CARD_PAD
        inner_w  = CARD_W - accent_w - CARD_PAD * 2

        lines = [
            l if isinstance(l, str) else ""
            for l in block.content
            if isinstance(l, str) and l.strip()
        ]

        hdr_h   = 7.0
        body_h  = len(lines) * LINE_H_BODY + 2.0
        total_h = hdr_h + body_h + CARD_PAD * 2

        self._check_page_break(total_h + CARD_GAP)
        y = self.get_y()

        self._draw_card_shell(
            MARGIN, y, CARD_W, total_h,
            COLOR_FORMULA_BG, COLOR_FORMULA_BD
        )
        self._draw_left_accent(
            MARGIN, y, total_h,
            COLOR_FORMULA_ACC, accent_w
        )

        body_y = self._card_header(
            MARGIN, y, block.title,
            COLOR_FORMULA_ACC, (255, 255, 255),
            font_size=8.5
        )

        self.set_font(FONT_MONO, "", 8.0)
        self._set_text(COLOR_TEXT_PRIMARY)
        cur_y = body_y + CARD_PAD

        for line in lines:
            self.set_xy(inner_x, cur_y)
            self.cell(
                inner_w, LINE_H_BODY,
                _strip_markdown_inline(line),
                border=0
            )
            cur_y += LINE_H_BODY

        self.set_y(y + total_h + CARD_GAP)

    def draw_text_card(self, block: Block):
        """
        Fallback for plain prose blocks.
        Neutral card, no accent.
        """
        inner_x = MARGIN + CARD_PAD
        inner_w = CARD_W - CARD_PAD * 2

        lines = [
            _strip_markdown_inline(l)
            for l in block.content
            if isinstance(l, str) and l.strip()
        ]
        text = "\n".join(lines)

        hdr_h   = 7.0
        body_h  = self._estimate_multiline_h(text, inner_w)
        total_h = hdr_h + body_h + CARD_PAD * 2

        self._check_page_break(total_h + CARD_GAP)
        y = self.get_y()

        self._draw_card_shell(
            MARGIN, y, CARD_W, total_h,
            COLOR_TEXT_CARD_BG, COLOR_TEXT_CARD_BD
        )

        body_y = self._card_header(
            MARGIN, y, block.title,
            COLOR_TEXT_CARD_BD,
            COLOR_TEXT_PRIMARY,
            font_size=8.5
        )

        self._multiline_text(
            inner_x, body_y + CARD_PAD,
            inner_w, text,
            font_size=8.0
        )

        self.set_y(y + total_h + CARD_GAP)


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

def build_revision_pdf(
    revision_notes_path: str | Path,
    output_path: str | Path,
    revision_metadata_path: str | Path | None = None
):
    """
    Build a revision PDF from revision_notes.md.

    Reads the combined markdown file, splits by chapter
    (--- separator), parses each chapter into Blocks,
    and renders them as a card-based PDF, preceded by a
    cover page built from revision_metadata.json.

    Args:
        revision_notes_path    : path to revision_notes.md
        output_path            : path to write the .pdf
        revision_metadata_path : path to revision_metadata.json.
                                  Defaults to a sibling file named
                                  "revision_metadata.json" next to
                                  revision_notes_path. If that file
                                  doesn't exist, the cover page is
                                  skipped and chapters start on page 1
                                  (keeps this function working even
                                  before metadata is wired up).
    """

    revision_notes_path = Path(revision_notes_path)
    output_path         = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if revision_metadata_path is None:
        revision_metadata_path = (
            revision_notes_path.parent / "revision_metadata.json"
        )
    revision_metadata_path = Path(revision_metadata_path)

    raw = revision_notes_path.read_text(
        encoding="utf-8"
    )

    # Split into per-chapter sections (same separator
    # used by combine_revision_notes)
    chapters_raw = raw.split("\n\n---\n\n")

    pdf = RevisionPDF()
    pdf.setup()

    if revision_metadata_path.exists():
        import json
        from revision_notes.revision_models import RevisionMetadata

        metadata_raw = json.loads(
            revision_metadata_path.read_text(encoding="utf-8")
        )
        # Support both the full RevisionNotes shape ({"metadata": {...}, ...})
        # and a bare RevisionMetadata dict.
        metadata_dict = metadata_raw.get("metadata", metadata_raw)
        metadata = RevisionMetadata(**metadata_dict)
        pdf.add_cover_page(metadata)

    pdf.new_content_page()

    for chapter_md in chapters_raw:

        chapter_md = chapter_md.strip()
        if not chapter_md:
            continue

        title, blocks = parse_revision_markdown(
            chapter_md
        )

        if title:
            pdf.add_chapter_divider(title)

        for block in blocks:
            pdf.draw_block(block)

    pdf.output(str(output_path))