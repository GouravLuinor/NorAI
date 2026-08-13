"""Anki `.apkg` package builder for NorAI flashcard decks (P6.2).

Zero LLM calls. Takes the deterministic 0-LLM card data (front / back /
explanation) that the pipeline already writes next to every lecture and wraps
it in a valid Anki package using the pinned `genanki` library (pure Python,
isolated to this module so swapping the writer later is a one-file change).

Conventions:
  * One deck per export: `NorAI · <lecture title>`.
  * Each card carries a per-chapter + per-lecture tag so chapters stay
    filterable inside Anki (genanki makes multi-deck packages fragile).
  * Card guids are stable (derived from chapter + front text), so re-importing
    an updated deck doesn't duplicate cards.
"""

from __future__ import annotations

import html
import io
import re
from typing import Iterable

import genanki

MODEL_ID = 8259124567915
DECK_ID_SEED = 291381607
MODEL_NAME = "NorAI Basic Card"


def _fnv1a_64(text: str) -> int:
    """FNV-1a 64-bit hash, kept inside the positive signed 64-bit range."""
    h = 0xCBF29CE484222325
    for ch in text.encode("utf-8"):
        h = ((h ^ ch) * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return h & 0x7FFFFFFFFFFFFFFF


def stable_id(*parts: str | int) -> int:
    """Deterministic int id derived from string parts (deck/model ids)."""
    return _fnv1a_64("\x1f".join(str(p) for p in parts))


def _browse_lines(text: str) -> str:
    """Escape text and preserve line breaks as <br/> for Anki HTML fields."""
    return html.escape(text or "").replace("\n", "<br/>")


def _clean_tag(text: str) -> str:
    """Anki tags must be single tokens — collapse whitespace to underscores."""
    return re.sub(r"\s+", "_", (text or "").strip())


def _card_html(front: str, back: str, explanation: str | None) -> str:
    """Full back-field markup: answer, then (optionally) the explanation hint."""
    parts = [_browse_lines(back)]
    if explanation:
        parts.append(
            f'<div class="hint"><span class="hint-label">Hint</span>{_browse_lines(explanation)}</div>'
        )
    return "".join(parts)


def _build_model() -> genanki.Model:
    return genanki.Model(
        MODEL_ID,
        MODEL_NAME,
        fields=[
            {"name": "Front"},
            {"name": "Back"},
            {"name": "Hint"},
        ],
        templates=[
            {
                "name": "NorAI Card",
                "qfmt": '<div class="front">{{Front}}</div>',
                "afmt": '<div class="back">{{Front}}<hr/>{{Back}}{{#Hint}}<div class="hint">{{Hint}}</div>{{/Hint}}</div>',
            }
        ],
        css=(
            ".card{font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;"
            "font-size:18px;line-height:1.5;text-align:left;color:#1a1a1a;padding:8px}"
            ".front{font-weight:600}.back{color:#333}.hint{margin-top:14px;padding:10px 12px;"
            "background:#f4f2ec;border-left:3px solid #b0413e;font-size:0.92em;color:#555}"
            ".hint-label{display:inline-block;font-weight:700;color:#b0413e;margin-right:6px}"
        ),
    )


def build_package(
    cards: Iterable[dict],
    deck_name: str = "NorAI",
    lecture_tag: str = "norai",
) -> bytes:
    """Build an Anki deck package's raw bytes.

    ``cards``: iterable of ``{front, back, explanation, chapter_title,
    chapter_id}`` dicts. Returns the full `.apkg` payload in memory (suitable
    for streaming to the client or for offline tests).
    """
    model = _build_model()
    deck = genanki.Deck(
        stable_id(DECK_ID_SEED, deck_name),
        deck_name,
        description="Created by NorAI from your lecture.",
    )
    deck.add_model(model)

    for card in cards:
        front = str(card.get("front") or "").strip()
        back = str(card.get("back") or "").strip()
        if not front or not back:
            continue  # skip degenerate cards — they can't be studied
        explanation = card.get("explanation") or ""
        chapter_title = str(card.get("chapter_title") or "").strip()
        chapter_id = card.get("chapter_id")

        tags = [lecture_tag]
        if chapter_id is not None:
            tags.append(f"chapter-{chapter_id}")
            tags.append(f"chapter:{_clean_tag(chapter_title)}")
        elif chapter_title:
            tags.append(f"chapter:{_clean_tag(chapter_title)}")

        note = genanki.Note(
            model=model,
            fields=[
                _browse_lines(front),
                _card_html(front, back, explanation),
                _browse_lines(explanation),
            ],
            tags=tags,
            guid=stable_id(deck_name, chapter_title, front),
        )
        deck.add_note(note)

    package = genanki.Package(deck)
    buf = io.BytesIO()
    package.write_to_file(buf)
    return buf.getvalue()