VISUAL_PROMPT = """
You are extracting educational knowledge from lecture screenshots.

Do NOT merely describe images. Focus on what a student should learn from these screenshots.
Treat all screenshots as belonging to the same lecture segment. Analyze all screenshots
together. Your goal is to extract the educational knowledge being taught, not to describe
the screenshots.

Think like a student creating revision notes. Focus on concepts, explanations, relationships,
algorithms, formulas, diagrams, and problem-solving ideas rather than visual appearance.

Return ONLY valid JSON matching this schema exactly:
{
    "visual_summary": "",
    "visual_notes": "",
    "ocr_text": "",
    "concepts": [],
    "note_worthy_concepts": [],
    "important_information": [],
    "formulas": [],
    "code_snippets": [],
    "visual_type": "",
    "teaching_stage": "",
    "importance_score": 0,
    "importance_reason": "",
    "include_in_notes": false,
    "selected_image_indices": []
}

Rules:
- visual_summary: Summarize the visual content.
- ocr_text: Extract only educationally useful text. Omit random labels, video player
  controls, timeline scrubbers, closed caption overlays, watermarks, drawing artifacts,
  and repeated text. Combine text from all screenshots into clean readable form.
- concepts: Concepts being taught.
- note_worthy_concepts: Only concepts that deserve their own section in notes.
- important_information: Important educational information.
- formulas: Mathematical formulas, time complexities, or equations.
- code_snippets: Important visible code snippets.
- visual_type: one of diagram, formula, code, graph, table, slide, other.
- teaching_stage: one of definition, intuition, example, construction, algorithm,
  complexity, application, summary, other.
- importance_score: 1-10.
- importance_reason: Why this screenshot group is important for students.
- include_in_notes: true only if the screenshots contain genuinely useful educational
  content.
- selected_image_indices: Indices of screenshots that should appear in final notes, using
  0-based indexing (e.g. [0], [1, 3], [0, 2, 4]). Select only educationally valuable
  screenshots. Do not select duplicates, intermediate drawing steps, or partially completed
  diagrams. Prefer complete explanations, complete diagrams, important formulas, and final
  results.
- visual_notes: A concise explanation that could be inserted directly into lecture notes.
  Assume the reader has not seen the screenshots. Explain the concept being taught, not the
  image itself.

IMPORTANT:
- Do not use LaTeX or backslash commands. Use plain text only. Example: "O(log n)", not
  "\\log n".
- Return ONLY valid JSON. Do not include markdown, code blocks, explanations, or any text
  before or after the JSON.
"""