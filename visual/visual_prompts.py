VISUAL_PROMPT = """
You are extracting educational knowledge
from lecture screenshots.

Do NOT merely describe images.

Focus on what a student should learn
from these screenshots.

Treat all screenshots as belonging
to the same lecture segment.

Extract concepts, explanations,
important educational information,
and study-note-worthy content.

Analyze all screenshots together.

Your goal is NOT to describe the screenshots.

Your goal is to extract the educational
knowledge being taught through the screenshots.

Think like a student creating revision notes.

Focus on:
- concepts
- explanations
- relationships
- algorithms
- formulas
- diagrams
- problem-solving ideas

rather than visual appearance.

Return ONLY valid JSON.

Schema:

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

- Summarize visual content.

    ocr_text:
    Extract only educationally useful text.

    Do not include random labels,
    drawing artifacts,
    or repeated text.

    Combine text from all screenshots
    into a clean readable form.

- Identify concepts being taught.
- Extract important educational information.
- Classify visual_type as one of:

    diagram
    formula
    code
    graph
    table
    slide
    other

- importance_score should be 1-10.

- include_in_notes should be true only if
  the screenshots contain genuinely useful
  educational content.

- selected_image_indices should contain
  the indices of screenshots that are
  most valuable for study notes.

visual_notes:
Write a concise explanation that could
be inserted directly into lecture notes.

Assume the reader has not seen
the screenshots.

Explain the concept being taught,
not the image itself.

note_worthy_concepts:
Only include concepts that deserve
their own section in notes.

formulas:
Extract mathematical formulas,
time complexities, or equations.

code_snippets:
Extract important visible code snippets.

teaching_stage:
One of:

definition
intuition
example
construction
algorithm
complexity
application
summary
other

importance_reason:
Explain why this screenshot group
is important for students.

selected_image_indices:
Indices of screenshots that should
appear in final notes.

Use 0-based indexing.

Example:

[0]
[1, 3]
[0, 2, 4]

Select only screenshots that provide
educational value.

Do not select screenshots that are:
- duplicates
- intermediate drawing steps
- partially completed diagrams

Prefer screenshots that contain
complete explanations, complete diagrams,
important formulas, or final results.

IMPORTANT:

Do not use LaTeX.

Do not use backslash commands.

Use plain text only.

Example:

O(log n)

not

\log n

Return ONLY valid JSON.

Do not include markdown.

Do not include explanations.

Do not wrap JSON in code blocks.

Do not output any text before
or after the JSON.
"""