"""
citations.py — P3.3: verify the tutor's "Sources" citations against the chunks
that were actually retrieved.

The model is instructed to end its answer with a **Sources** list of the study
note sections that contributed. Previously those names were taken on trust and
never checked. This module:

  1. parse_citations(answer)  — extract the bulleted section names.
  2. verify_citations(answer, chunks) — match each cited name against the
     retrieved chunk heading/heading_path, and tag it verified/unverified with
     the matching chunk_id.

Deterministic, no LLM call. Verified citations flow to the API and the frontend
References panel; unverified ones are dropped so fabricated sections never
appear as references.
"""

from __future__ import annotations

import re

_MD_OR_HR_RE = re.compile(r"^(#{1,6}\s|[-*_]{3,}\s*$)")
_BULLET_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)]|[*_]{1,2})\s*")

# Stop tokens: anything after the Sources list that isn't a bullet/continuation
# is treated as trailing chatter (the model occasionally adds a closing line).
_STOP_WORDS = ("would you like", "want to", "let me know", "hope this")


def _is_sources_header(line: str) -> bool:
    """True for any 'Sources' header line (handles **Sources**, '**Sources:**',
    'Sources •', 'Sources:', leading/trailing whitespace)."""
    t = re.sub(r"[\*_:•\-\s]", "", line).lower()
    return t == "sources"


def _normalize(text: str) -> str:
    """Lowercase, strip markdown/bullets, collapse whitespace."""
    t = re.sub(r"[*_`#]", "", text or "")
    t = _BULLET_RE.sub(" ", t)
    return re.sub(r"\s+", " ", t).strip().lower()


def parse_citations(answer: str) -> list[str]:
    """
    Extract the section names from the answer's Sources list.
    Uses the LAST Sources header; collects bullet items to the end, stopping at
    a markdown heading, an HR, or a likely closing line.
    """
    if not answer:
        return []

    lines = answer.splitlines()
    last_header = -1
    for i, line in enumerate(lines):
        if _is_sources_header(line.strip()):
            last_header = i

    if last_header < 0:
        return []

    citations: list[str] = []
    for line in lines[last_header + 1:]:
        stripped = line.strip()
        if not stripped:
            continue
        if _MD_OR_HR_RE.match(stripped):
            break
        if _is_sources_header(stripped):
            break
        cleaned = _BULLET_RE.sub("", stripped).strip()
        if not cleaned:
            continue
        low = cleaned.lower()
        if any(low.startswith(w) for w in _STOP_WORDS):
            break
        citations.append(cleaned)
    return citations


def _chunk_candidates(chunk: dict) -> list[str]:
    return [chunk.get("heading_path") or "", chunk.get("heading") or ""]


def _best_chunk_for(citation_norm: str, chunks: list[dict]) -> dict | None:
    """P2.5: deterministic citation→chunk matching.

    Old behaviour was first-match-wins over a bidirectional substring test,
    which bound short/generic names ("Intro", "Summary") — and duplicate
    headings — to whichever chunk happened to come first. Now:
      1. exact normalized match on any candidate wins outright;
      2. otherwise containment matches compete, most-specific (longest
         normalized candidate) wins, with alphabetical tiebreak.
    """
    best: tuple[dict, tuple[int, str]] | None = None
    for chunk in chunks:
        for cand in _chunk_candidates(chunk):
            cn = _normalize(cand)
            if not cn:
                continue
            if cn == citation_norm:
                return chunk  # exact match: nothing can beat it
            if citation_norm in cn or cn in citation_norm:
                key = (len(cn), cn)
                if best is None or key > best[1]:
                    best = (chunk, key)
    return best[0] if best else None


def verify_citations(answer: str, chunks: list[dict]) -> list[dict]:
    """
    Verify every cited section against `chunks`. Returns:
        [
          {"section": str, "verified": bool,
           "chunk_id": str|None, "heading_path": str|None, "heading": str|None},
          ...
        ]
    """
    result: list[dict] = []
    for citation in parse_citations(answer):
        norm = _normalize(citation)
        match = _best_chunk_for(norm, chunks)
        result.append(
            {
                "section": citation,
                "verified": match is not None,
                "chunk_id": (match or {}).get("chunk_id"),
                "heading_path": (match or {}).get("heading_path"),
                "heading": (match or {}).get("heading"),
                "chapter_id": (match or {}).get("chapter_id"),
            }
        )
    return result


def verified_citations(answer: str, chunks: list[dict]) -> list[dict]:
    """Convenience: only the verified citations (drop unverified)."""
    return [c for c in verify_citations(answer, chunks) if c["verified"]]
