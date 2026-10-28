"""
timestamp_check.py — how far a transcript's segment times are from the real
speech times, using YouTube's own captions as ground truth (no LLM call).

Each segment's first 4 words are located in the caption word stream; the
error is segment start minus caption time. Prints median / p90 error and the
median per 2-minute bucket, which shows drift.

Get captions (free):
    venv/bin/yt-dlp --skip-download --write-auto-subs --sub-langs en \
        --sub-format json3 -o "%(id)s" <youtube-url>
Usage:
    venv/bin/python -m tutor.evals.timestamp_check <id>.en.json3 outputs/<lecture>/transcripts/<id>.json [...]

The max can be large when a 4-word phrase repeats in the lecture; trust the
median and p90.
"""

from __future__ import annotations

import json
import re
import sys


def _norm(text: str) -> list[str]:
    return re.sub(r"[^a-z ]", "", text.lower().replace("\n", " ")).split()


def caption_words(path: str) -> list[tuple[str, float]]:
    words = []
    for event in json.load(open(path, encoding="utf-8"))["events"]:
        if "segs" not in event:
            continue
        text = "".join(s.get("utf8", "") for s in event["segs"])
        words.extend((w, event["tStartMs"] / 1000) for w in _norm(text))
    return words


def check(captions: list[tuple[str, float]], transcript_path: str) -> str:
    words = [w for w, _ in captions]

    def find(text: str) -> float | None:
        key = _norm(text)[:4]
        if len(key) < 4:
            return None
        for i in range(len(words) - 4):
            if words[i:i + 4] == key:
                return captions[i][1]
        return None

    data = json.load(open(transcript_path, encoding="utf-8"))
    segments = data.get("segments", data)
    pairs = [(g, s["start"] - g) for s in segments if (g := find(s["text"])) is not None]
    if not pairs:
        return f"{transcript_path}\n  no segments matched the captions"
    errs = sorted(abs(e) for _, e in pairs)
    end = max(g for g, _ in pairs)
    buckets = []
    for lo in range(0, int(end) + 1, 120):
        b = sorted(e for g, e in pairs if lo <= g < lo + 120)
        buckets.append(f"{lo // 60}m:{b[len(b) // 2]:+.0f}" if b else f"{lo // 60}m:-")
    words_total = sum(len(s["text"].split()) for s in segments)
    return (
        f"{transcript_path}\n"
        f"  segs {len(segments)} words {words_total} matched {len(pairs)} "
        f"median|err| {errs[len(errs) // 2]:.1f}s p90 {errs[int(len(errs) * .9)]:.1f}s max {errs[-1]:.1f}s\n"
        f"  {' '.join(buckets)}"
    )


def main() -> None:
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    captions = caption_words(sys.argv[1])
    for path in sys.argv[2:]:
        print(check(captions, path))


if __name__ == "__main__":
    main()
