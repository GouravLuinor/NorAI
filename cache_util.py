"""
cache_util.py — hash-of-inputs caching helpers for expensive pipeline stages.

Pipeline stages that make paid LLM calls (knowledge extraction, screenshot
selection, consolidated chapter artifacts) are idempotent given their inputs.
Each such stage writes a small `.inputs.sha256` marker next to its outputs.
On a re-run, if every output exists AND the marker matches a fresh hash of the
stage's current inputs, the stage is skipped so re-runs cost ~0 API calls.

The hash is keyed on the stage's *inputs* (never just "file exists"), so a
re-run with changed inputs always recomputes. See ROADMAP P1.4.
"""

import hashlib
import json
from pathlib import Path


def _file_digest(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def digest(*sources) -> str:
    """
    Compute a stable digest over the stage's inputs.

    Each source may be:
      - a path (str/Path) to an existing file  -> hashed by content
      - any other str                          -> hashed as a literal
      - a dict/list                             -> hashed as sorted JSON
      - anything else                           -> hashed via str()
    """
    h = hashlib.sha256()
    for src in sources:
        if isinstance(src, Path):
            src = str(src)
        if isinstance(src, str):
            p = Path(src)
            if p.is_file():
                h.update(b"F:")
                h.update(_file_digest(p).encode())
            else:
                h.update(b"S:")
                h.update(src.encode())
        elif isinstance(src, (dict, list)):
            h.update(b"J:")
            h.update(json.dumps(src, sort_keys=True).encode())
        else:
            h.update(b"O:")
            h.update(str(src).encode())
        h.update(b"\x00")
    return h.hexdigest()


def outputs_current(marker: Path, outputs: list, *sources) -> bool:
    """True if all outputs exist and the marker matches the current inputs."""
    if not all(Path(o).exists() for o in outputs):
        return False
    if not Path(marker).is_file():
        return False
    try:
        return Path(marker).read_text().strip() == digest(*sources)
    except OSError:
        return False


def write_marker(marker: Path, *sources) -> None:
    """Persist the current input digest next to a stage's outputs."""
    marker = Path(marker)
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(digest(*sources))
