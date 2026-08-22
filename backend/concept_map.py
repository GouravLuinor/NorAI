"""
backend/concept_map.py — zero-LLM concept-graph builder (P5.1 extraction).

Pure file-read logic moved verbatim from the GET /concept-map handler in
main.py so the endpoint stays thin.
"""
import json as json_lib
import re
from pathlib import Path


def build_concept_map(base: Path, chapter_id: int) -> dict:
    """Derive a visual concept graph for a chapter from existing output JSONs."""
    outline_path = base / "notes" / "lecture_outline.json"

    lecture_title = "Lecture Mind Map"
    chapter_title = f"Chapter {chapter_id}"
    focus_concepts = []
    summary = ""

    if outline_path.exists():
        try:
            with open(outline_path, encoding="utf-8") as f:
                outline = json_lib.load(f)
                lecture_title = outline.get("lecture_title", lecture_title)
                for ch in outline.get("chapters", []):
                    cid = ch.get("chapter_id") or ch.get("id")
                    if int(cid) == chapter_id:
                        chapter_title = ch.get("title", chapter_title)
                        focus_concepts = ch.get("focus_concepts", [])
                        summary = ch.get("summary", "")
                        break
        except Exception:
            pass

    notes_json_paths = [
        base / "notes" / f"chapter_{chapter_id}.json",
        base / "notes" / f"notes_chapter_{chapter_id}.json",
    ]

    sections_raw = []
    important_info = []
    for np in notes_json_paths:
        if np.exists():
            try:
                with open(np, encoding="utf-8") as f:
                    notes_data = json_lib.load(f)
                    sections_raw = notes_data.get("sections", [])
                    important_info = notes_data.get("important_information", []) + notes_data.get("inferred_knowledge", [])
                break
            except Exception:
                pass

    root_id = f"ch-{chapter_id}"
    nodes = []
    edges = []

    nodes.append({
        "id": root_id,
        "label": chapter_title,
        "type": "root",
        "category": "Chapter",
        "description": summary or f"Core concept structure for {chapter_title}",
    })

    if not focus_concepts and sections_raw:
        focus_concepts = [re.sub(r"^\d+[\.\s\-]+", "", s.get("title", "")).strip() for s in sections_raw if s.get("title")]

    if not focus_concepts:
        focus_concepts = [f"Section {i+1}" for i in range(len(sections_raw))] or ["Core Concepts"]

    seen_labels = set()

    used_sections = set()

    for i, fc in enumerate(focus_concepts):
        node_id = f"fc-{chapter_id}-{i}"
        fc_lower = fc.lower()
        node_desc = ""
        matched_section = None

        best_sec = None
        best_score = 0

        for sec_idx, sec in enumerate(sections_raw):
            stitle = sec.get("title", "").lower()
            content = sec.get("content_markdown", "").lower()
            score = 0

            if re.search(r'\b' + re.escape(fc_lower) + r'\b', stitle):
                score = 10
            elif fc_lower in stitle:
                score = 7
            elif re.search(r'\b' + re.escape(fc_lower) + r'\b', content):
                score = 5
            elif fc_lower in content:
                score = 3

            if sec_idx in used_sections:
                score = score // 3

            if score > best_score:
                best_score = score
                best_sec = (sec_idx, sec)

        if best_sec:
            sec_idx, sec = best_sec
            used_sections.add(sec_idx)
            matched_section = sec
            content = sec.get("content_markdown", "")
            clean_text = re.sub(r"[\*`#|_]|<[^>]+>", "", content).strip()
            sentences = [s.strip() for s in clean_text.split(".") if len(s.strip()) > 15]
            if sentences:
                node_desc = ". ".join(sentences[:2]) + "."
                if len(node_desc) > 220:
                    node_desc = node_desc[:217] + "..."

        if not node_desc and i < len(sections_raw) and i not in used_sections:
            used_sections.add(i)
            sec = sections_raw[i]
            content = sec.get("content_markdown", "")
            clean_text = re.sub(r"[\*`#|_]|<[^>]+>", "", content).strip()
            sentences = [s.strip() for s in clean_text.split(".") if len(s.strip()) > 15]
            if sentences:
                node_desc = ". ".join(sentences[:2]) + "."
                if len(node_desc) > 220:
                    node_desc = node_desc[:217] + "..."

        if not node_desc:
            node_desc = f"{fc} — Key architectural concept covered in {chapter_title}."

        nodes.append({
            "id": node_id,
            "label": fc,
            "type": "focus_concept",
            "category": "Core Concept",
            "description": node_desc,
        })
        edges.append({
            "id": f"edge-root-{node_id}",
            "source": root_id,
            "target": node_id,
            "label": "",
        })

        sub_items = []
        if matched_section and matched_section.get("content_markdown"):
            lines = matched_section["content_markdown"].split("\n")
            for line in lines:
                # Filter out table delimiters (| :--- | :--- |), code blocks (```), and non-text artifacts
                if re.search(r'[:\-]{2,}', line) or (line.strip().startswith('|') and ':' in line):
                    continue
                if line.strip().startswith('```') or line.strip().startswith('import ') or line.strip().startswith('export '):
                    continue

                clean_line = re.sub(r"^[\|\-\*\s\d\.]+", "", line).strip()
                clean_line = re.sub(r"[\*`#|_]|<[^>]+>", "", clean_line).strip()

                if not re.search(r'[a-zA-Z]{4,}', clean_line):
                    continue

                if clean_line and len(clean_line) > 10 and clean_line not in seen_labels:
                    sub_items.append(clean_line)
                    seen_labels.add(clean_line)
                    if len(sub_items) >= 2:
                        break

        if not sub_items and important_info:
            for item in important_info:
                clean_item = re.sub(r"^[\|\-\*\s\d\.]+", "", str(item)).strip()
                clean_item = re.sub(r"[\*`#|_]|<[^>]+>", "", clean_item).strip()
                if re.search(r'[a-zA-Z]{4,}', clean_item) and clean_item not in seen_labels:
                    sub_items.append(clean_item)
                    seen_labels.add(clean_item)
                    if len(sub_items) >= 2:
                        break

        for j, item_text in enumerate(sub_items):
            detail_id = f"dc-{chapter_id}-{i}-{j}"
            first_sentence = item_text.split(".")[0].strip()
            short_label = first_sentence[:45] + "..." if len(first_sentence) > 45 else first_sentence

            nodes.append({
                "id": detail_id,
                "label": short_label,
                "type": "detail",
                "category": "Mechanism",
                "description": item_text,
            })
            edges.append({
                "id": f"edge-{node_id}-{detail_id}",
                "source": node_id,
                "target": detail_id,
                "label": "details",
            })

    return {
        "lecture_title": lecture_title,
        "chapter_id": chapter_id,
        "root": {"id": root_id, "label": chapter_title, "summary": summary},
        "nodes": nodes,
        "edges": edges,
    }
